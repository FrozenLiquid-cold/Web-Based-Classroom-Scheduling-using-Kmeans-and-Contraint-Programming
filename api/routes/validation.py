"""Route for validating schedule changes."""
from datetime import datetime, timedelta
import logging
from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import or_

from api import models
from api import schemas
from api.db import SessionLocal

validation_bp = Blueprint("validation", __name__)
logger = logging.getLogger(__name__)



def times_overlap(start1, end1, start2, end2):
    """Check if two time ranges overlap."""
    if not (start1 and end1 and start2 and end2):
        return False
    # Overlap if one starts before the other ends
    return max(start1, start2) < min(end1, end2)

def get_minutes(t):
    """Get minutes from midnight."""
    return t.hour * 60 + t.minute

@validation_bp.route("/schedule-item", methods=["POST"])
def validate_schedule_item():
    """Validate a proposed schedule item against constraints."""
    payload = request.get_json(force=True) or {}
    try:
        req = schemas.ScheduleValidationRequest(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = SessionLocal()
    messages = []
    
    try:

        # Pydantic has handled basic type checks
        # Decide which days to check: prefer day_ids if present, else day_id
        days_to_check = req.day_ids if req.day_ids else [req.day_id]
        if not days_to_check or all(d is None for d in days_to_check):
             return jsonify({"valid": False, "messages": ["No valid day selected"]}), 400

        # Parse proposed times
        start_time = parse_time(req.start_time)
        end_time = parse_time(req.end_time)
        
        if not start_time or not end_time:
            return jsonify({"valid": False, "messages": ["Invalid time format"]}), 400
            
        if start_time >= end_time:
            return jsonify({"valid": False, "messages": ["End time must be after start time"]}), 400

        # Collect all conflicts
        
        # We need to check conflicts separately for EACH day
        # because the schedule for Monday might differ from Wednesday (e.g. room available on M but not W)
        
        for check_day_id in days_to_check:
             if check_day_id is None: continue

             # Base query for existing schedule on THIS day
             query = db.query(models.Schedule).filter(
                 models.Schedule.day_id == check_day_id,
                 models.Schedule.semester == req.semester,
                 models.Schedule.year == req.year  
                 # Filtering by year here assumes we only check conflicts within same academic year schedule
                 # However, room/instructor conflicts are global across years.
                 # Let's relax year filter for Room and Instructor checks? 
                 # Usually scheduling is done per semester/term, so `semester` is key overlap.
                 # If instructor teaches 1st Year course and 4th Year course, they conflict regardless of 'year' field.
                 # BUT, the `models.Schedule` usually contains ALL active schedules for the active term.
                 # So filtering by `semester` is correct. Filtering by `year` (year level) is WRONG for global resources.
                 # Let's FIX this: Remove year filter for global resources (Room, Instructor).
                 # Keep year filter for Student Group (since meaningful student blocks are per year level).
             ).filter(models.Schedule.semester == req.semester)

             if req.id:
                 query = query.filter(models.Schedule.id != req.id)

             # 1. Check Room Conflict (Active Term Global Resource)
             if req.room_id:
                 # Note: Removed .filter(year) for global check
                 # We need a fresh query that covers ALL years for this room/day/sem
                 room_query = db.query(models.Schedule).filter(
                     models.Schedule.day_id == check_day_id,
                     models.Schedule.semester == req.semester,
                     models.Schedule.room_id == req.room_id
                 )
                 if req.id:
                     room_query = room_query.filter(models.Schedule.id != req.id)
                     
                 room_conflicts = room_query.all()
                 logger.info(f"Checking Room {req.room_id} on Day {check_day_id}. Found {len(room_conflicts)} potential items.")
                 
                 for item in room_conflicts:
                     i_start, i_end = _parse_schedule_time(item.time)
                     logger.info(f"Comparing proposed [{start_time}-{end_time}] vs Item {item.id} [{i_start}-{i_end}] (raw: '{item.time}')")
                     
                     if times_overlap(start_time, end_time, i_start, i_end):
                         messages.append(f"Room Conflict (Day {check_day_id}): Room is occupied by {item.subject_id} at this time.")
                         logger.info("Conflict FOUND!")


             # 2. Check Instructor Conflict (Active Term Global Resource)
             if req.instructor_id:
                 instr_query = db.query(models.Schedule).filter(
                     models.Schedule.day_id == check_day_id,
                     models.Schedule.semester == req.semester,
                     models.Schedule.instructor_id == req.instructor_id
                 )
                 if req.id:
                     instr_query = instr_query.filter(models.Schedule.id != req.id)

                 instr_conflicts = instr_query.all()
                 for item in instr_conflicts:
                     i_start, i_end = _parse_schedule_time(item.time)
                     if times_overlap(start_time, end_time, i_start, i_end):
                         messages.append(f"Instructor Conflict (Day {check_day_id}): Instructor is teaching {item.subject_id} at this time.")

                 # 4. Check Travel Time (Only if no direct conflict)
                 if req.room_id:
                     proposed_room = db.query(models.Room).get(req.room_id)
                     if proposed_room and proposed_room.building_id:
                         others = []
                         for item in instr_conflicts:
                             s, e = _parse_schedule_time(item.time)
                             if s and e:
                                 others.append({
                                     "start": s, 
                                     "end": e, 
                                     "room_id": item.room_id,
                                 })
                         others.sort(key=lambda x: x["start"])
                         
                         prev_class = None
                         next_class = None
                         for item in others:
                             if item["end"] <= start_time:
                                 prev_class = item
                             if item["start"] >= end_time and next_class is None:
                                 next_class = item

                         if prev_class and prev_class["room_id"]:
                             prev_room = db.query(models.Room).get(prev_class["room_id"])
                             if prev_room and prev_room.building_id and prev_room.building_id != proposed_room.building_id:
                                 dist = _get_travel_time(db, prev_room.building_id, proposed_room.building_id)
                                 gap = (get_minutes(start_time) - get_minutes(prev_class["end"]))
                                 if gap < dist:
                                     messages.append(f"Travel Time Warning (Day {check_day_id}): Only {gap} mins gap after previous class.")

                         if next_class and next_class["room_id"]:
                             next_room = db.query(models.Room).get(next_class["room_id"])
                             if next_room and next_room.building_id and next_room.building_id != proposed_room.building_id:
                                 dist = _get_travel_time(db, proposed_room.building_id, next_room.building_id)
                                 gap = (get_minutes(next_class["start"]) - get_minutes(end_time))
                                 if gap < dist:
                                     messages.append(f"Travel Time Warning (Day {check_day_id}): Only {gap} mins gap before next class.")


             # 3. Check Student Group Conflict (Specific Year Level Resource)
             # Here we use the generic query that filtered by year
             student_query = query.filter(
                 models.Schedule.course_id == req.course_id,
                 models.Schedule.year == req.year
                 # check_day_id is already in `query` definition? 
                 # Wait, original `query` definition included `day_id == req.day_id` which might be None if we use day_ids list
                 # We need to rebuild `query` for each day loop or rely on my custom queries above.
                 # Let's rebuild student query safely.
             )
             
             # Re-define student query specifically for this day/year
             student_query = db.query(models.Schedule).filter(
                 models.Schedule.day_id == check_day_id,
                 models.Schedule.semester == req.semester,
                 models.Schedule.year == req.year,
                 models.Schedule.course_id == req.course_id
             )
             if req.id:
                 student_query = student_query.filter(models.Schedule.id != req.id)

             if req.block and hasattr(models.Schedule, 'block'):
                 student_query = student_query.filter(models.Schedule.block == req.block)
             
             student_conflicts = student_query.all()
             for item in student_conflicts:
                  i_start, i_end = _parse_schedule_time(item.time)
                  if times_overlap(start_time, end_time, i_start, i_end):
                      messages.append(f"Student Conflict (Day {check_day_id}): Group has another class {item.subject_id} at this time.")

        return jsonify({
            "valid": len(messages) == 0,
            "messages": messages
        })

    except Exception as e:
        logger.exception("Validation error")
        return jsonify({"valid": False, "messages": [str(e)]}), 500
    finally:
        db.close()

def parse_time(t_str):
    """Parse HH:MM (24h) or HH:MM AM/PM string to time object."""
    if not t_str:
        return None
    t_str = t_str.strip()
    # Try 24-hour format first
    try:
        return datetime.strptime(t_str, "%H:%M").time()
    except ValueError:
        pass
        
    # Try 12-hour format with AM/PM
    try:
        return datetime.strptime(t_str, "%I:%M %p").time()
    except ValueError:
        pass

    # Handle non-padded 12-hour hour (e.g. "7:30 AM") on platforms where %I requires padding
    # Only if format is "H:MM AM/PM"
    if len(t_str) > 0 and t_str[1] == ':':
         try:
             # Pad with leading zero
             padded = "0" + t_str
             return datetime.strptime(padded, "%I:%M %p").time()
         except ValueError:
             pass

    # Try 12-hour format without space before AM/PM (rare but possible)
    try:
        return datetime.strptime(t_str, "%I:%M%p").time()
    except ValueError:
        pass
        
    return None

def _parse_schedule_time(time_str):
    """Parse 'HH:MM - HH:MM' or 'HH:MM' string from DB (supports 12h/24h)."""
    if not time_str:
        return None, None
    
    time_str = time_str.replace("–", "-").replace("—", "-")  # Normalize dashes
    parts = time_str.split("-")
    
    try:
        if len(parts) >= 2:
            start = parse_time(parts[0].strip())
            end = parse_time(parts[1].strip())
            # If start/end parsed successfully, return them
            if start and end:
                return start, end
            else:
                 # If parsing failed, maybe it's "7:30 AM - 9:00 AM" but split failed due to spaces?
                 # No, split('-') works. 
                 # Maybe the format is different? Just fallback to None.
                 return None, None
        elif len(parts) == 1:
            # Maybe it's just "7:30 AM"?
            # Assume 1 hour duration or just return None (safer for strict overlap)
            return None, None
    except:
        return None, None
    return None, None

def _get_travel_time(db, b1_id, b2_id):
    """Get travel time between two buildings."""
    if b1_id == b2_id:
        return 0
    
    # Check A->B
    d = db.query(models.BuildingDistance).filter(
        models.BuildingDistance.from_building_id == b1_id,
        models.BuildingDistance.to_building_id == b2_id
    ).first()
    if d: return d.travel_time_minutes
    
    # Check B->A (symmetric)
    d = db.query(models.BuildingDistance).filter(
        models.BuildingDistance.from_building_id == b2_id,
        models.BuildingDistance.to_building_id == b1_id
    ).first()
    if d: return d.travel_time_minutes
    
    return 0
