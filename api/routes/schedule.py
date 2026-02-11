"""Schedule routes implemented with Flask blueprints."""
import logging
import os
import sys
import time
from pathlib import Path

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

logger = logging.getLogger(__name__)

# Ensure the project root is in the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api import models
from api import schemas
from api.db import SessionLocal
from api.job_queue import queue_manager
from api.scheduler.scheduler import load_schedule, save_schedule as persist_schedule
from api.scheduler.course_scheduler import schedule_course_refactored
from sqlalchemy.orm import joinedload

schedule_bp = Blueprint("schedule", __name__)


def _get_session() -> SessionLocal:
    return SessionLocal()


@schedule_bp.route("/room", methods=["GET"])
def get_room_schedule():
    """Get schedule for a specific room, semester, and optional day."""
    room_id = request.args.get("room_id", type=int)
    semester = request.args.get("semester", type=int)
    day_id = request.args.get("day_id", type=int)
    
    if not room_id or not semester:
         return jsonify({"detail": "room_id and semester are required"}), 400

    session = _get_session()
    try:
        query = session.query(models.Schedule).filter(
            models.Schedule.room_id == room_id,
            models.Schedule.semester == semester
        )
        
        if day_id:
            query = query.filter(models.Schedule.day_id == day_id)
            
        # Eager load relationships
        query = query.options(
            joinedload(models.Schedule.subject),
            joinedload(models.Schedule.instructor),
            joinedload(models.Schedule.day)
        )
        
        schedules = query.all()
        
        results = []
        for s in schedules:
            instructor_name = ""
            if s.instructor:
                instructor_name = f"{s.instructor.first_name} {s.instructor.last_name}"
                
            results.append({
                "id": s.id,
                "time": s.time,
                "day_id": s.day_id,
                "day_label": s.day.label if s.day else "",
                "subject_code": s.subject.code if s.subject else "",
                "subject_description": s.subject.description if s.subject else "",
                "type": s.subject.type if s.subject else "",
                "instructor_name": instructor_name,
                "block": s.block,
                "year": s.year,
                "semester": s.semester
            })
            
        return jsonify(results)
    except Exception as e:
        return jsonify({"detail": str(e)}), 500
    finally:
        session.close()


@schedule_bp.route("/course", methods=["POST"])
def schedule_course_endpoint():
    """Schedule a single course for a specific year/semester using KMeans + CP-SAT."""
    payload = request.get_json(force=True) or {}

    required_fields = ["course_id", "year", "semester", "blocks_count"]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        return (
            jsonify({"detail": f"Missing required fields: {', '.join(missing)}"}),
            422,
        )

    try:
        course_id = int(payload["course_id"])
        year = int(payload["year"])
        semester = int(payload["semester"])
        blocks_count = int(payload["blocks_count"])
    except (TypeError, ValueError):
        return jsonify({"detail": "course_id, year, semester, and blocks_count must be integers"}), 422

    session = _get_session()
    try:
        result = schedule_course_refactored(
            session=session,
            course_id=course_id,
            year=year,
            semester=semester,
            blocks_count=blocks_count,
        )
        status_code = 200 if result["status"] == "scheduled" else 409
        response = jsonify(result)
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, status_code
    except Exception as exc:
        session.rollback()
        response = jsonify({"status": "error", "detail": str(exc)})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500
    finally:
        session.close()


@schedule_bp.route("/generate", methods=["POST", "OPTIONS"])
def generate_schedule():
    """Queue (or reuse) a scheduling job and return immediately."""
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "*")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    payload = request.get_json(force=True) or {}
    try:
        schedule_request = schemas.ScheduleGenerateRequest(**payload)
    except ValidationError as exc:
        response = jsonify({"detail": exc.errors()})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 422

    wait_seconds = request.args.get("wait_seconds", type=int)
    logger = logging.getLogger(__name__)
    start_time = time.time()

    db = _get_session()
    try:
        course = (
            db.query(models.Course)
            .filter(models.Course.id == schedule_request.course_id)
            .first()
        )
        if not course:
            response = jsonify({"detail": "Course not found"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 404

        college_id = course.college_id
        k_clusters = (
            schedule_request.k_clusters
            if schedule_request.k_clusters is not None
            else 3
        )

        if schedule_request.years:
            years = sorted({int(y) for y in schedule_request.years if y is not None})
        elif schedule_request.year is not None:
            years = [int(schedule_request.year)]
        else:
            years = [1, 2, 3, 4]

        if not years:
            response = jsonify({"detail": "No year levels provided"})
            response.headers.add("Access-Control-Allow-Origin", "*")
            return response, 400

        years_key = "-".join(str(y) for y in years)
        queue_key = (
            f"sched:{college_id}:course{schedule_request.course_id}:"
            f"sem{schedule_request.semester}:years{years_key}:k{k_clusters}:blocks{schedule_request.blocks_count or 1}"
        )

        job_payload = {
            "course_id": schedule_request.course_id,
            "years": years,
            "semester": schedule_request.semester,
            "subject_ids": schedule_request.subject_ids,
            "use_kmeans": schedule_request.use_kmeans
            if schedule_request.use_kmeans is not None
            else True,
            "k_clusters": k_clusters,
            "weight_slots": schedule_request.weight_slots
            if schedule_request.weight_slots is not None
            else 2.0,
            "force_refit": getattr(schedule_request, "force_refit", False),
            "block_capacities": [
                override.model_dump()
                for override in (schedule_request.block_capacities or [])
            ],
            "blocks_count": schedule_request.blocks_count,
        }

        job_id, already_queued = queue_manager.enqueue(queue_key, job_payload)

        if already_queued:
            logger.info(
                "Scheduling job already queued/running for %s — reusing job_id=%s",
                queue_key,
                job_id,
            )
    finally:
        db.close()

    if wait_seconds and wait_seconds > 0:
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            status_obj = queue_manager.get_status(job_id)
            if status_obj.get("status") in {"succeeded", "failed"}:
                elapsed = time.time() - start_time
                if status_obj["status"] == "succeeded":
                    result = status_obj.get("result") or {}
                    # Extract items array (result may be {"items": [...], "count": N} or just [...])
                    if isinstance(result, dict) and "items" in result:
                        items = result["items"]
                    elif isinstance(result, list):
                        items = result
                    else:
                        items = []
                    
                    response = jsonify(
                        {
                            "status": "success",
                            "job_id": job_id,
                            "course_id": schedule_request.course_id,
                            "years": years,
                            "semester": schedule_request.semester,
                            "items": items,  # For backward compatibility
                            "scheduled": items, # For frontend compatibility (calls it .scheduled)
                            "result": items,  # New: direct array for frontend
                            "diagnostics": result.get("diagnostics", {}),
                            "count": len(items),
                            "count": len(items),
                            "elapsed_time": round(elapsed, 2),
                            "already_queued": already_queued,
                        }
                    )
                    response.headers.add("Access-Control-Allow-Origin", "*")
                    return response, 200
                response = jsonify(
                    {
                        "detail": status_obj.get("error")
                        or "Scheduling job failed"
                    }
                )
                response.headers.add("Access-Control-Allow-Origin", "*")
                return response, 500
            time.sleep(0.25)

    elapsed = time.time() - start_time
    response = jsonify(
        {
            "status": "queued",
            "job_id": job_id,
            "course_id": schedule_request.course_id,
            "college_id": college_id,
            "years": years,
            "semester": schedule_request.semester,
            "elapsed_time": round(elapsed, 2),
            "already_queued": already_queued,
        }
    )
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response, 202


@schedule_bp.route("/status", methods=["GET"])
def get_schedule_status():
    """Check status of a queued scheduling job."""
    job_id = request.args.get("job_id")
    if not job_id:
        response = jsonify({"detail": "job_id query parameter is required"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 400
    status_obj = queue_manager.get_status(job_id)
    if status_obj.get("status") == "not_found":
        response = jsonify({"detail": "Job not found"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 404
    
    # Transform response to match frontend expectations
    # Frontend expects: {"status": "completed", "result": [scheduled_items...]}
    if status_obj.get("status") == "succeeded":
        result_data = status_obj.get("result", {})
        
        # DEBUG DIAGNOSTICS
        raw_diag = result_data.get("diagnostics", {}) if isinstance(result_data, dict) else {}
        print(f"DEBUG: API route sending diagnostics check. JobID={job_id}, Keys={len(raw_diag)}")
        if len(raw_diag) > 0:
            sample_k = next(iter(raw_diag))
            print(f"DEBUG: Sample diag: {raw_diag[sample_k]}")
        else:
            print(f"DEBUG: DIAGNOSTICS EMPTY IN API ROUTE! Result keys: {result_data.keys() if isinstance(result_data, dict) else 'Not a dict'}")

        # Extract items array from result (result may be {"items": [...], "count": N} or just [...])
        if isinstance(result_data, dict) and "items" in result_data:
            scheduled_items = result_data["items"]
        elif isinstance(result_data, list):
            scheduled_items = result_data
        else:
            scheduled_items = []
        
        response = jsonify({
            "status": "completed",
            "result": scheduled_items,
            "diagnostics": raw_diag,
            "job_id": status_obj.get("job_id"),
            "created_at": status_obj.get("created_at"),
            "started_at": status_obj.get("started_at"),
            "finished_at": status_obj.get("finished_at"),
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    
    # For other statuses (pending, running, failed), return as-is
    response = jsonify(status_obj)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response


@schedule_bp.route("/save", methods=["POST"])
def save_schedule_route():
    """Save schedule to database."""
    payload = request.get_json(force=True) or {}
    try:
        save_request = schemas.ScheduleSaveRequest(**payload)
    except ValidationError as exc:
        response = jsonify({"detail": exc.errors()})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 422

    db = _get_session()
    try:
        course = (
            db.query(models.Course)
            .filter(models.Course.id == save_request.course_id)
            .first()
        )
        if not course:
            return jsonify({"detail": "Course not found"}), 404

        schedule_items = [item.model_dump() for item in save_request.items]
        saved_records = persist_schedule(
            db=db,
            course_id=save_request.course_id,
            year=save_request.year,
            semester=save_request.semester,
            schedule_items=schedule_items,
        )
        return jsonify(
            {
                "status": "success",
                "message": "Schedule saved successfully",
                "count": len(saved_records),
            }
        )
    finally:
        db.close()


@schedule_bp.route("/load", methods=["GET"])
def load_schedule_route():
    """Load schedule from database. Aggregates all years if year is not specified."""
    try:
        course_id = int(request.args["course_id"])
        semester = int(request.args["semester"])
    except KeyError as missing:
        return jsonify({"detail": f"Missing parameter: {missing.args[0]}"}), 400
    except ValueError:
        return jsonify({"detail": "course_id and semester must be integers"}), 400

    year = request.args.get("year", type=int)
    instructor_id = request.args.get("instructor_id", type=int)

    # Check if there's an active job for this course/semester
    active_job_id = queue_manager.find_active_job_for_course(course_id, semester)
    if active_job_id:
        return jsonify({
            "status": "pending",
            "message": "Schedule generation in progress",
            "job_id": active_job_id,
        }), 200

    db = _get_session()
    try:
        # If year is specified, load only that year
        if year is not None:
            schedules = load_schedule(
                db=db,
                course_id=course_id,
                year=year,
                semester=semester,
                instructor_id=instructor_id,
            )
            items = [
                {
                    "id": sched.id,
                    "subject_id": sched.subject_id,
                    "instructor_id": sched.instructor_id,
                    "room_id": sched.room_id,
                    "day_id": sched.day_id,
                    "time": sched.time,
                    "course_id": sched.course_id,
                    "year": sched.year,
                    "semester": sched.semester,
                    "block": getattr(sched, "block", None),
                }
                for sched in schedules
            ]
        else:
            # Aggregate all years for this course/semester
            # Use stored procedure for optimized query (year=None returns all years)
            import db_procedures
            schedules_list = db_procedures.get_schedules_for_course(
                db=db,
                course_id=course_id,
                semester=semester,
                year=None,  # None means all years
                instructor_id=instructor_id
            )
            
            # Deduplicate by subject_id (keep first occurrence)
            seen_subjects = set()
            unique_schedules = []
            for sched in schedules_list:
                if sched.subject_id not in seen_subjects:
                    seen_subjects.add(sched.subject_id)
                    unique_schedules.append(sched)
            
            items = [
                {
                    "id": sched.id,
                    "subject_id": sched.subject_id,
                    "instructor_id": sched.instructor_id,
                    "room_id": sched.room_id,
                    "day_id": sched.day_id,
                    "time": sched.time,
                    "course_id": sched.course_id,
                    "year": sched.year,
                    "semester": sched.semester,
                    "block": getattr(sched, "block", None),
                }
                for sched in unique_schedules
            ]
        
        return jsonify(
            {
                "status": "success",
                "course_id": course_id,
                "year": year,
                "semester": semester,
                "items": items,
                "count": len(items),
            }
        )
    finally:
        db.close()


@schedule_bp.route("/load-instructor", methods=["GET"])
def load_instructor_schedule():
    """
    Load all schedules for an instructor in a single optimized query.
    
    This endpoint eliminates the N+1 query problem on the instructor Schedule page
    by returning all schedules for an instructor across all courses in one call.
    
    Query params:
        instructor_id: Required. The instructor's ID.
        semester: Optional. Filter by semester (1 or 2).
    
    Returns:
        {
            "status": "success",
            "instructor_id": <id>,
            "semester": <semester or null>,
            "items": [...schedule items...],
            "course_ids": [list of unique course IDs with schedules],
            "count": <total count>
        }
    """
    instructor_id = request.args.get("instructor_id", type=int)
    if not instructor_id:
        response = jsonify({"detail": "instructor_id query parameter is required"})
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 400
    
    semester = request.args.get("semester", type=int)
    
    db = _get_session()
    try:
        # Use direct ORM query for reliable cross-database compatibility
        # This leverages the idx_schedules_instructor_id index for optimization
        query = db.query(models.Schedule).filter(
            models.Schedule.instructor_id == instructor_id
        )
        if semester is not None:
            query = query.filter(models.Schedule.semester == semester)
        
        query = query.order_by(
            models.Schedule.course_id,
            models.Schedule.semester,
            models.Schedule.year,
            models.Schedule.day_id,
            models.Schedule.time
        )
        
        schedules = query.all()
        
        # Build items list and collect unique course IDs
        course_ids = set()
        items = []
        for sched in schedules:
            course_ids.add(sched.course_id)
            items.append({
                "id": sched.id,
                "subject_id": sched.subject_id,
                "instructor_id": sched.instructor_id,
                "room_id": sched.room_id,
                "day_id": sched.day_id,
                "time": sched.time,
                "course_id": sched.course_id,
                "year": sched.year,
                "semester": sched.semester,
                "block": getattr(sched, "block", None),
            })
        
        response = jsonify({
            "status": "success",
            "instructor_id": instructor_id,
            "semester": semester,
            "items": items,
            "course_ids": sorted(list(course_ids)),
            "count": len(items),
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    except Exception as e:
        logging.getLogger(__name__).error(f"Error loading instructor schedules: {e}")
        response = jsonify({
            "status": "error",
            "detail": str(e),
            "items": [],
            "course_ids": [],
            "count": 0
        })
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response, 500
    finally:
        db.close()


@schedule_bp.route("/delete", methods=["DELETE"])
def delete_schedule():
    """Delete schedule from database."""
    try:
        course_id = int(request.args["course_id"])
        year = int(request.args["year"])
        semester = int(request.args["semester"])
    except KeyError as missing:
        return jsonify({"detail": f"Missing parameter: {missing.args[0]}"}), 400
    except ValueError:
        return jsonify({"detail": "course_id, year, and semester must be integers"}), 400

    db = _get_session()
    try:
        deleted = (
            db.query(models.Schedule)
            .filter(
                models.Schedule.course_id == course_id,
                models.Schedule.year == year,
                models.Schedule.semester == semester,
            )
            .delete()
        )
        db.commit()
        return jsonify(
            {
                "status": "success",
                "message": f"Deleted {deleted} schedule entries",
            }
        )
    finally:
        db.close()


@schedule_bp.route("/item/<int:schedule_id>", methods=["DELETE"])
def delete_schedule_item(schedule_id):
    """Delete a single schedule item by ID."""
    db = _get_session()
    try:
        deleted = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).delete()
        db.commit()
        if deleted:
            return jsonify({"status": "success", "message": "Schedule item deleted"}), 200
        else:
            return jsonify({"detail": "Schedule item not found"}), 404
    except Exception as e:
        db.rollback()
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()


@schedule_bp.route("/suggestions", methods=["GET"])
def get_scheduling_suggestions():
    """Get alternative slot suggestions for a failed subject."""
    subject_id = request.args.get("subject_id", type=int)
    course_id = request.args.get("course_id", type=int)
    year = request.args.get("year", type=int)
    semester = request.args.get("semester", type=int)

    if not all([subject_id, course_id, year, semester]):
        return jsonify({"detail": "Missing required parameters"}), 400

    from api.scheduler.scheduler import get_suggestions
    
    session = _get_session()
    try:
        suggestions = get_suggestions(
            db=session,
            subject_id=subject_id,
            course_id=course_id,
            year=year,
            semester=semester
        )
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        logger.error(f"Error fetching suggestions: {e}")
        return jsonify({"detail": str(e)}), 500
    finally:
        session.close()



@schedule_bp.route("/availability", methods=["GET"])
def check_availability():
    """Check availability of rooms/instructors for a specific time window."""
    semester = request.args.get("semester", type=int)
    year = request.args.get("year", type=int)
    day_id = request.args.get("day_id", type=int)
    start_time = request.args.get("start_time") # HH:MM string, or we parse? function expects mins.
    # Actually function expects start_min, end_min. 
    # Let's accept start_min, end_min directly to avoid re-parsing here, or parse if string.
    # Or just pass the time string logic?
    # The frontend usually works with HH:MM 24h or similar.
    # The `check_resource_availability` function uses `start_min`, `end_min`.
    # Let's check what the frontend sends. Usually it sends strings.
    # But `check_resource_availability` logic expects start_min/end_min AND parses inside?
    # No, I implemented `check_resource_availability` to take `start_min`, `end_min` but it also has internal `parse_time_range`?
    # Wait, my implementation of `check_resource_availability` HAS a `parse_time_range` helper but it uses it on EXISTING schedules.
    # It takes `start_min` and `end_min` as integers for the QUERY/REQUEST.
    # So I need to parse inputs here.
    
    start_min = request.args.get("start_min", type=int)
    end_min = request.args.get("end_min", type=int)
    
    subject_id = request.args.get("subject_id", type=int)
    
    if not all([semester, year, day_id, start_min is not None, end_min is not None]):
         return jsonify({"detail": "Missing required parameters"}), 400
         
    from api.scheduler.scheduler import check_resource_availability
    
    session = _get_session()
    try:
        result = check_resource_availability(
            db=session,
            semester=semester,
            year=year,
            day_id=day_id,
            start_min=start_min,
            end_min=end_min,
            subject_id=subject_id
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return jsonify({"detail": str(e)}), 500
    finally:
        session.close()
