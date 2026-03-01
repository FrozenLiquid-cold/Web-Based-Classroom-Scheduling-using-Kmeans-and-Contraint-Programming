from flask import Blueprint, jsonify, request
from sqlalchemy import func
from api.db import SessionLocal
from api import models
import logging

stats_bp = Blueprint("stats", __name__)
logger = logging.getLogger(__name__)

def _get_session():
    return SessionLocal()

@stats_bp.route("/admin", methods=["GET"])
def get_admin_stats():
    """Get basic admin statistics."""
    db = _get_session()
    try:
        semester = request.args.get("semester", default=1, type=int)
        department_id = request.args.get("department_id", default=None, type=int)
        
        # 1. Room Availability / Utilization
        # Capacity per room: 12 hours (7am-7pm) * 6 days (M-S) = 72 hours = 4320 mins
        ROOM_CAPACITY_MINS = 72 * 60
        
        rooms = db.query(models.Room).all()
        total_rooms = len(rooms)
        
        # Calculate usage per room
        room_usage = {} # room_id -> used_mins
        
        schedules_query = db.query(models.Schedule).filter(models.Schedule.semester == semester)
        if department_id:
            schedules_query = schedules_query.join(models.Course).filter(models.Course.college_id == department_id)
            
        schedules = schedules_query.all()
        
        scheduled_subject_ids = set()
        
        # Calculate usage and find conflicts
        slots_map = {} # (room_id, day_id, time) -> [schedule_objs]

        for sched in schedules:
            if sched.subject_id:
                scheduled_subject_ids.add(sched.subject_id)
            
            # Simple duration estimation (default 90 mins)
            duration = 90 
            if sched.room_id:
                room_usage[sched.room_id] = room_usage.get(sched.room_id, 0) + duration
            
            # Group for conflict detection
            if sched.room_id and sched.day_id and sched.time:
                key = (sched.room_id, sched.day_id, sched.time)
                if key not in slots_map:
                    slots_map[key] = []
                slots_map[key].append(sched)

        conflict_details = []
        conflict_count = 0
        total_conflicting_items = 0
        
        for key, items in slots_map.items():
            if len(items) > 1:
                conflict_count += 1
                total_conflicting_items += len(items)
                
                # Format for frontend
                room_obj = items[0].room
                day_obj = items[0].day
                
                conflict_group = {
                    "room": room_obj.name if room_obj else f"Room {key[0]}",
                    "day": day_obj.label if day_obj else f"Day {key[1]}",
                    "time": key[2],
                    "items": []
                }
                
                for item in items:
                    subj = item.subject
                    conflict_group["items"].append({
                        "id": item.id,
                        "subject_code": subj.code if subj else "Unknown",
                        "description": subj.description if subj else "",
                        "instructor": f"{item.instructor.first_name} {item.instructor.last_name}" if item.instructor else "TBA"
                    })
                
                conflict_details.append(conflict_group)

        # Room Stats
        active_rooms = sum(1 for r in rooms if room_usage.get(r.id, 0) > 0)
        avg_utilization = 0
        if rooms:
            total_used_mins = sum(room_usage.values())
            total_capacity = total_rooms * ROOM_CAPACITY_MINS
            avg_utilization = (total_used_mins / total_capacity) * 100 if total_capacity > 0 else 0

        # 2. Instructor Availability / Load
        instructors_query = db.query(models.Instructor)
        if department_id:
            instructors_query = instructors_query.filter(models.Instructor.college_id == department_id)
            
        instructors = instructors_query.all()
        total_instructors = len(instructors)
        
        active_instructor_ids = set(s.instructor_id for s in schedules if s.instructor_id)
        active_instructors = len(active_instructor_ids)
        
        # 3. Unscheduled Subjects
        subjects_total_query = db.query(models.Subject).filter(models.Subject.semester == semester)
        if department_id:
            subjects_total_query = subjects_total_query.join(models.Course).filter(models.Course.college_id == department_id)
            
        total_subjects = subjects_total_query.count()
        unscheduled_count = total_subjects - len(scheduled_subject_ids)
        if unscheduled_count < 0: unscheduled_count = 0 

        # Fetch a few unscheduled for display
        unscheduled_sample = []
        if unscheduled_count > 0:
             unscheduled_query = db.query(models.Subject).filter(
                 models.Subject.semester == semester,
                 models.Subject.id.notin_(scheduled_subject_ids)
             )
             if department_id:
                 unscheduled_query = unscheduled_query.join(models.Course).filter(models.Course.college_id == department_id)
             
             unscheduled_objs = unscheduled_query.limit(5).all()
             unscheduled_sample = [{"code": s.code, "description": s.description} for s in unscheduled_objs]

        # 4. Recommendations
        recommendations = []
        if avg_utilization > 80:
             recommendations.append("High room utilization detected. Consider adding more rooms or extending hours.")
        if conflict_count > 0:
             recommendations.append(f"Found {conflict_count} schedule conflicts. Please resolve them using the conflict resolution tool.")
        if unscheduled_count > 0:
             recommendations.append(f"{unscheduled_count} subjects are unscheduled. Use the Schedule Generator to assign them.")
        
        if not recommendations:
             recommendations.append("System is running smoothly. No critical issues detected.")

        return jsonify({
            "rooms": {
                "total": total_rooms,
                "active": active_rooms,
                "utilization_pct": round(avg_utilization, 1)
            },
            "instructors": {
                "total": total_instructors,
                "active": active_instructors,
                "utilization_pct": round((active_instructors/total_instructors)*100, 1) if total_instructors else 0
            },
            "conflicts": {
                "count": conflict_count,
                "affected_items": total_conflicting_items,
                "details": conflict_details
            },
            "subjects": {
                "total": total_subjects,
                "scheduled": len(scheduled_subject_ids),
                "unscheduled": unscheduled_count,
                "sample_unscheduled": unscheduled_sample
            },
            "recommendations": recommendations
        })

    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}", exc_info=True)
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()
