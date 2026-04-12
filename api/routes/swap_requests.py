"""
API routes for instructor schedule swap requests.

Allows instructors to:
- Search for compatible schedules to swap with
- Create swap requests
- View incoming/outgoing requests
- Accept or reject swap requests
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging

from ..db import SessionLocal
from ..models import SwapRequest, Schedule, Instructor, Room, Day, Subject

logger = logging.getLogger(__name__)

swap_requests_bp = Blueprint("swap_requests", __name__, url_prefix="/api/swap-requests")


def get_instructor_id_from_user(user_id, session):
    """Get instructor ID from user ID"""
    instructor = session.query(Instructor).filter(Instructor.user_id == user_id).first()
    return instructor.id if instructor else None


@swap_requests_bp.route("/search", methods=["POST"])
def search_swappable_schedules():
    """
    Search for schedules that can be swapped with.
    
    Request body:
    {
        "instructor_id": 1,
        "schedule_id": 5,  # The schedule the instructor wants to swap away
        "time_range_start": 480,  # Optional: start time in minutes from midnight (8:00 AM)
        "time_range_end": 720,    # Optional: end time in minutes from midnight (12:00 PM)
        "day_ids": [1, 3],        # Optional: list of day IDs to search
        "room_type": "LEC"        # Optional: LEC or LAB
    }
    """
    data = request.get_json()
    instructor_id = data.get("instructor_id")
    schedule_id = data.get("schedule_id")
    
    if not instructor_id:
        return jsonify({"error": "instructor_id is required"}), 400
    
    session = SessionLocal()
    try:
        # Get the requester's schedule to know what we're swapping away
        requester_schedule = None
        if schedule_id:
            requester_schedule = session.query(Schedule).get(schedule_id)
        
        # Build query for schedules available to swap with (including own schedules for self-swap)
        query = session.query(Schedule).filter(
            Schedule.instructor_id.isnot(None)
        )
        
        # Exclude the specific schedule being swapped (can't swap with itself)
        if schedule_id:
            query = query.filter(Schedule.id != schedule_id)
        
        # Filter by time range if provided
        time_range_start = data.get("time_range_start")
        time_range_end = data.get("time_range_end")
        
        # Note: We need to parse the time field or use start_min/end_min if available
        # For now, we'll return all and filter on frontend if needed
        
        # Filter by days if provided
        day_ids = data.get("day_ids")
        if day_ids:
            query = query.filter(Schedule.day_id.in_(day_ids))
        
        # Filter by room type if provided
        room_type = data.get("room_type")
        if room_type:
            query = query.join(Room).filter(Room.type == room_type)
        
        # Filter by year/semester to match current schedule
        if requester_schedule:
            query = query.filter(
                Schedule.year == requester_schedule.year,
                Schedule.semester == requester_schedule.semester
            )
        
        # Eager load relationships
        query = query.options(
            joinedload(Schedule.instructor),
            joinedload(Schedule.room),
            joinedload(Schedule.day),
            joinedload(Schedule.subject)
        )
        
        schedules = query.limit(50).all()
        
        # Format results
        results = []
        for s in schedules:
            instructor_name = ""
            if s.instructor:
                instructor_name = f"{s.instructor.first_name or ''} {s.instructor.last_name or ''}".strip()
            
            schedule_data = {
                "id": s.id,
                "subject_id": s.subject_id,
                "subject_code": s.subject.code if s.subject else None,
                "subject_description": s.subject.description if s.subject else None,
                "instructor_id": s.instructor_id,
                "instructor_name": instructor_name,
                "room_id": s.room_id,
                "room_name": s.room.name if s.room else None,
                "day_id": s.day_id,
                "day_label": s.day.label if s.day else None,
                "time": s.time,
                "block": s.block,
                "year": s.year,
                "semester": s.semester
            }
            
            # Calculate conflicts if requester schedule is known
            if requester_schedule:
                conflicts = validate_swap_conflicts(session, requester_schedule, s)
                schedule_data["conflicts"] = conflicts
                schedule_data["has_conflict"] = len(conflicts) > 0
            else:
                schedule_data["conflicts"] = []
                schedule_data["has_conflict"] = False
                
            results.append(schedule_data)
        
        return jsonify({"schedules": results}), 200
        
    except Exception as e:
        logger.error(f"Error searching schedules: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@swap_requests_bp.route("", methods=["POST"])
def create_swap_request():
    """
    Create a new swap request.
    
    Request body:
    {
        "requester_schedule_id": 5,
        "target_schedule_id": 10,
        "requester_id": 1,
        "reason": "I prefer morning classes"
    }
    """
    data = request.get_json()
    
    requester_schedule_id = data.get("requester_schedule_id")
    target_schedule_id = data.get("target_schedule_id")
    requester_id = data.get("requester_id")
    reason = data.get("reason", "")
    
    if not all([requester_schedule_id, target_schedule_id, requester_id]):
        return jsonify({"error": "requester_schedule_id, target_schedule_id, and requester_id are required"}), 400
    
    session = SessionLocal()
    try:
        # Get schedules
        requester_schedule = session.query(Schedule).get(requester_schedule_id)
        target_schedule = session.query(Schedule).get(target_schedule_id)
        
        if not requester_schedule or not target_schedule:
            return jsonify({"error": "Invalid schedule IDs"}), 400
        
        # Verify requester owns the schedule
        if requester_schedule.instructor_id != requester_id:
            return jsonify({"error": "You can only swap your own schedules"}), 403
        
        # Get target instructor
        target_id = target_schedule.instructor_id
        if not target_id:
            return jsonify({"error": "Target schedule has no instructor"}), 400
        
        # Check for existing pending request
        existing = session.query(SwapRequest).filter(
            SwapRequest.requester_schedule_id == requester_schedule_id,
            SwapRequest.target_schedule_id == target_schedule_id,
            SwapRequest.status == "pending"
        ).first()
        
        if existing:
            return jsonify({"error": "A pending request already exists for this swap"}), 400
        
        # Validate: Check if swap would create conflicts
        # This validation should check both instructors' full schedules
        conflicts = validate_swap_conflicts(session, requester_schedule, target_schedule)
        if conflicts:
            return jsonify({"error": "Swap would create conflicts", "conflicts": conflicts}), 400
        
        # Create the request
        swap_request = SwapRequest(
            requester_schedule_id=requester_schedule_id,
            target_schedule_id=target_schedule_id,
            requester_id=requester_id,
            target_id=target_id,
            reason=reason,
            status="pending"
        )
        
        session.add(swap_request)
        session.commit()
        
        return jsonify({
            "message": "Swap request created successfully",
            "id": swap_request.id
        }), 201
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating swap request: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@swap_requests_bp.route("/validate", methods=["POST"])
def validate_swap_request():
    """
    Check for conflicts without creating a request.
    
    Request body:
    {
        "requester_schedule_id": 5,
        "target_schedule_id": 10
    }
    """
    data = request.get_json()
    requester_schedule_id = data.get("requester_schedule_id")
    target_schedule_id = data.get("target_schedule_id")
    
    if not requester_schedule_id or not target_schedule_id:
        return jsonify({"error": "requester_schedule_id and target_schedule_id are required"}), 400
        
    session = SessionLocal()
    try:
        requester_schedule = session.query(Schedule).get(requester_schedule_id)
        target_schedule = session.query(Schedule).get(target_schedule_id)
        
        if not requester_schedule or not target_schedule:
            return jsonify({"error": "Invalid schedule IDs"}), 400
            
        conflicts = validate_swap_conflicts(session, requester_schedule, target_schedule)
        
        return jsonify({"conflicts": conflicts}), 200
        
    except Exception as e:
        logger.error(f"Error validating swap: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def validate_swap_conflicts(session, schedule_a, schedule_b):
    """
    Check if swapping these schedules would create conflicts.
    
    After swap:
    - Instructor A teaches at schedule_b's time/day/room
    - Instructor B teaches at schedule_a's time/day/room
    
    Need to check:
    1. Instructor time conflicts (does instructor have another class at new time?)
    2. Student/block conflicts (does block have another class at new time?)
    3. Room conflicts (is room already occupied at new time?)
    """
    """
    Check if swapping these schedules would create conflicts.
    Returns a list of conflict dictionaries:
    {
        "type": "instructor" | "student" | "room",
        "role": "requester" | "target" | "both",
        "entity": "Name of entity",
        "message": "Description of conflict",
        "details": "Extra info"
    }
    """
    conflicts = []
    
    instructor_a_id = schedule_a.instructor_id
    instructor_b_id = schedule_b.instructor_id
    
    # Pre-fetch objects for names
    inst_a = session.query(Instructor).get(instructor_a_id)
    inst_b = session.query(Instructor).get(instructor_b_id)
    
    name_a = f"{inst_a.first_name} {inst_a.last_name}" if inst_a else "You"
    name_b = f"{inst_b.first_name} {inst_b.last_name}" if inst_b else "Target Instructor"
    
    # ---------------------------------------------------------
    # 1. INSTRUCTOR CONFLICTS
    # ---------------------------------------------------------
    
    # Scenario A: Instructor A (requester) takes Target's slot (schedule_b.time/day)
    # Check if Instructor A is already busy at that time
    conflict_a = session.query(Schedule).filter(
        Schedule.instructor_id == instructor_a_id,
        Schedule.day_id == schedule_b.day_id,
        Schedule.time == schedule_b.time,
        Schedule.year == schedule_b.year,
        Schedule.semester == schedule_b.semester,
        Schedule.id != schedule_a.id  # Don't count the class they are swapping away
    ).first()
    
    if conflict_a:
        conflicts.append({
            "type": "instructor",
            "role": "requester",
            "entity": name_a, # "You" usually
            "message": f"You are already teaching '{conflict_a.subject.code}' at this time.",
            "details": f"{conflict_a.subject.code} - {conflict_a.subject.description}" if conflict_a.subject else ""
        })
        
    # Scenario B: Instructor B (target) takes Requester's slot (schedule_a.time/day)
    conflict_b = session.query(Schedule).filter(
        Schedule.instructor_id == instructor_b_id,
        Schedule.day_id == schedule_a.day_id,
        Schedule.time == schedule_a.time,
        Schedule.year == schedule_a.year,
        Schedule.semester == schedule_a.semester,
        Schedule.id != schedule_b.id
    ).first()
    
    if conflict_b:
        conflicts.append({
            "type": "instructor",
            "role": "target",
            "entity": name_b,
            "message": f"{name_b} is already teaching '{conflict_b.subject.code}' at your time slot.",
            "details": f"{conflict_b.subject.code} - {conflict_b.subject.description}" if conflict_b.subject else ""
        })

    # ---------------------------------------------------------
    # 2. STUDENT BLOCK CONFLICTS
    # ---------------------------------------------------------
    
    # Block A (your students) moves to Target's time
    if schedule_a.block:
        block_conflict_a = session.query(Schedule).filter(
            Schedule.block == schedule_a.block,
            Schedule.course_id == schedule_a.course_id,
            Schedule.day_id == schedule_b.day_id,
            Schedule.time == schedule_b.time,
            Schedule.year == schedule_a.year,
            Schedule.semester == schedule_a.semester,
            Schedule.id != schedule_a.id
        ).first()
        
        if block_conflict_a:
            conflicts.append({
                "type": "student",
                "role": "requester",
                "entity": f"Block {schedule_a.block}",
                "message": f"Your class block {schedule_a.block} has another class '{block_conflict_a.subject.code}' at the target time.",
                "details": f"{block_conflict_a.subject.code} ({block_conflict_a.instructor.last_name})" if block_conflict_a.subject and block_conflict_a.instructor else ""
            })

    # Block B (target students) moves to Your time
    if schedule_b.block:
        block_conflict_b = session.query(Schedule).filter(
            Schedule.block == schedule_b.block,
            Schedule.course_id == schedule_b.course_id,
            Schedule.day_id == schedule_a.day_id,
            Schedule.time == schedule_a.time,
            Schedule.year == schedule_b.year,
            Schedule.semester == schedule_b.semester,
            Schedule.id != schedule_b.id
        ).first()
        
        if block_conflict_b:
            conflicts.append({
                "type": "student",
                "role": "target",
                "entity": f"Block {schedule_b.block}",
                "message": f"Target class block {schedule_b.block} has another class '{block_conflict_b.subject.code}' at your time slot.",
                "details": f"{block_conflict_b.subject.code} ({block_conflict_b.instructor.last_name})" if block_conflict_b.subject and block_conflict_b.instructor else ""
            })

    # ---------------------------------------------------------
    # 3. ROOM COMPATIBILITY CONFLICTS
    # ---------------------------------------------------------
    # Note: Traditional "Room Occupied" conflicts don't apply because we are swapping valid slots.
    # However, we should check if the new room is suitable for the class type.
    
    # Check if Room B (target room) is suitable for Subject A (your subject)
    if schedule_b.room and schedule_a.subject:
        # Check Type Mismatch (e.g. LAB subject in LEC room)
        # Only flag if strict mismatch: Subject is LAB but Room is LEC. 
        # (LEC subject in LAB room is usually allowed but maybe non-ideal)
        if schedule_a.subject.type == 'LAB' and schedule_b.room.type != 'LAB':
             conflicts.append({
                "type": "room",
                "role": "requester",
                "entity": schedule_b.room.name,
                "message": f"Target room '{schedule_b.room.name}' is a {schedule_b.room.type} room, but your subject is Laboratory.",
                "details": "Room Type Mismatch"
            })
            
    # Check if Room A (your room) is suitable for Subject B (target subject)
    if schedule_a.room and schedule_b.subject:
        if schedule_b.subject.type == 'LAB' and schedule_a.room.type != 'LAB':
             conflicts.append({
                "type": "room",
                "role": "target",
                "entity": schedule_a.room.name,
                "message": f"Your room '{schedule_a.room.name}' is a {schedule_a.room.type} room, but target subject is Laboratory.",
                "details": "Room Type Mismatch"
            })

    return conflicts


@swap_requests_bp.route("/incoming", methods=["GET"])
def get_incoming_requests():
    """Get swap requests sent TO this instructor"""
    instructor_id = request.args.get("instructor_id", type=int)
    
    if not instructor_id:
        return jsonify({"error": "instructor_id is required"}), 400
    
    session = SessionLocal()
    try:
        requests = session.query(SwapRequest).filter(
            SwapRequest.target_id == instructor_id
        ).options(
            joinedload(SwapRequest.requester_schedule).joinedload(Schedule.subject),
            joinedload(SwapRequest.requester_schedule).joinedload(Schedule.room),
            joinedload(SwapRequest.requester_schedule).joinedload(Schedule.day),
            joinedload(SwapRequest.target_schedule).joinedload(Schedule.subject),
            joinedload(SwapRequest.target_schedule).joinedload(Schedule.room),
            joinedload(SwapRequest.target_schedule).joinedload(Schedule.day),
            joinedload(SwapRequest.requester)
        ).order_by(SwapRequest.created_at.desc()).all()
        
        return jsonify({"requests": [format_swap_request(r) for r in requests]}), 200
        
    except Exception as e:
        logger.error(f"Error getting incoming requests: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@swap_requests_bp.route("/outgoing", methods=["GET"])
def get_outgoing_requests():
    """Get swap requests sent BY this instructor"""
    instructor_id = request.args.get("instructor_id", type=int)
    
    if not instructor_id:
        return jsonify({"error": "instructor_id is required"}), 400
    
    session = SessionLocal()
    try:
        requests = session.query(SwapRequest).filter(
            SwapRequest.requester_id == instructor_id
        ).options(
            joinedload(SwapRequest.requester_schedule).joinedload(Schedule.subject),
            joinedload(SwapRequest.requester_schedule).joinedload(Schedule.room),
            joinedload(SwapRequest.requester_schedule).joinedload(Schedule.day),
            joinedload(SwapRequest.target_schedule).joinedload(Schedule.subject),
            joinedload(SwapRequest.target_schedule).joinedload(Schedule.room),
            joinedload(SwapRequest.target_schedule).joinedload(Schedule.day),
            joinedload(SwapRequest.target)
        ).order_by(SwapRequest.created_at.desc()).all()
        
        return jsonify({"requests": [format_swap_request(r) for r in requests]}), 200
        
    except Exception as e:
        logger.error(f"Error getting outgoing requests: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def format_swap_request(r):
    """Format a SwapRequest for API response"""
    requester_name = ""
    if r.requester:
        requester_name = f"{r.requester.first_name or ''} {r.requester.last_name or ''}".strip()
    
    target_name = ""
    if r.target:
        target_name = f"{r.target.first_name or ''} {r.target.last_name or ''}".strip()
    
    return {
        "id": r.id,
        "requester_id": r.requester_id,
        "requester_name": requester_name,
        "target_id": r.target_id,
        "target_name": target_name,
        "requester_schedule": format_schedule(r.requester_schedule) if r.requester_schedule else None,
        "target_schedule": format_schedule(r.target_schedule) if r.target_schedule else None,
        "reason": r.reason,
        "status": r.status,
        "rejection_reason": r.rejection_reason,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "responded_at": r.responded_at.isoformat() if r.responded_at else None
    }


def format_schedule(s):
    """Format a Schedule for API response."""
    return {
        "id": s.id,
        "subject_code": s.subject.code if s.subject else None,
        "subject_description": s.subject.description if s.subject else None,
        "room_name": s.room.name if s.room else None,
        "day_label": s.day.label if s.day else None,
        "time": s.time,
        "block": s.block
    }



@swap_requests_bp.route("/<int:request_id>/accept", methods=["POST"])
def accept_swap_request(request_id):
    """Accept a swap request and execute the swap."""
    session = SessionLocal()
    try:
        swap_request = session.query(SwapRequest).get(request_id)
        
        if not swap_request:
            return jsonify({"error": "Swap request not found"}), 404
        
        if swap_request.status != "pending":
            return jsonify({"error": f"Request is already {swap_request.status}"}), 400
        
        # Get the schedules
        schedule_a = session.query(Schedule).get(swap_request.requester_schedule_id)
        schedule_b = session.query(Schedule).get(swap_request.target_schedule_id)
        
        if not schedule_a or not schedule_b:
            return jsonify({"error": "One or both schedules no longer exist"}), 400
        
        # Re-validate conflicts before executing
        conflicts = validate_swap_conflicts(session, schedule_a, schedule_b)
        if conflicts:
            return jsonify({"error": "Swap would create conflicts", "conflicts": conflicts}), 400
        
        # Execute the swap - exchange time, day, and room
        a_day_id = schedule_a.day_id
        a_time = schedule_a.time
        a_room_id = schedule_a.room_id
        
        b_day_id = schedule_b.day_id
        b_time = schedule_b.time
        b_room_id = schedule_b.room_id
        
        schedule_a.day_id = b_day_id
        schedule_a.time = b_time
        schedule_a.room_id = b_room_id
        
        schedule_b.day_id = a_day_id
        schedule_b.time = a_time
        schedule_b.room_id = a_room_id
        
        # Update request status
        swap_request.status = "accepted"
        swap_request.responded_at = datetime.utcnow()
        
        session.commit()
        
        return jsonify({
            "message": "Swap executed successfully",
            "swapped": True
        }), 200
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error accepting swap request: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@swap_requests_bp.route("/<int:request_id>/reject", methods=["POST"])
def reject_swap_request(request_id):
    """Reject a swap request"""
    data = request.get_json() or {}
    rejection_reason = data.get("reason", "")
    
    session = SessionLocal()
    try:
        swap_request = session.query(SwapRequest).get(request_id)
        
        if not swap_request:
            return jsonify({"error": "Swap request not found"}), 404
        
        if swap_request.status != "pending":
            return jsonify({"error": f"Request is already {swap_request.status}"}), 400
        
        swap_request.status = "rejected"
        swap_request.rejection_reason = rejection_reason
        swap_request.responded_at = datetime.utcnow()
        
        session.commit()
        
        return jsonify({
            "message": "Swap request rejected",
            "rejected": True
        }), 200
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error rejecting swap request: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@swap_requests_bp.route("/pending-count", methods=["GET"])
def get_pending_count():
    """Get count of pending incoming requests for notification badge"""
    instructor_id = request.args.get("instructor_id", type=int)
    
    if not instructor_id:
        return jsonify({"error": "instructor_id is required"}), 400
    
    session = SessionLocal()
    try:
        count = session.query(SwapRequest).filter(
            SwapRequest.target_id == instructor_id,
            SwapRequest.status == "pending"
        ).count()
        
        return jsonify({"count": count}), 200
        
    except Exception as e:
        logger.error(f"Error getting pending count: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
