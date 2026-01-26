"""CRUD routes for entities implemented with Flask blueprints."""
from typing import Iterable, List, Type
import logging
import hashlib
import re

from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .. import models
from .. import schemas
from ..db import SessionLocal

entities_bp = Blueprint("entities", __name__)
logger = logging.getLogger(__name__)


from contextlib import contextmanager

@contextmanager
def _get_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _safe_db_operation(func):
    """Decorator for safe database operations with automatic rollback on error."""
    def wrapper(*args, **kwargs):
        db = None
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            if db:
                db.rollback()
            logger.error(f"Database error in {func.__name__}: {e}", exc_info=True)
            raise
        except Exception as e:
            if db:
                db.rollback()
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper


def _serialize(instance, schema: Type[BaseModel]) -> dict:
    return schema.model_validate(instance).model_dump()


def _serialize_list(instances: Iterable, schema: Type[BaseModel]) -> List[dict]:
    return [schema.model_validate(obj).model_dump() for obj in instances]


def _time_str_to_minutes(value: str) -> int:
    value = (value or "").strip()
    if not value:
        raise ValueError("empty")

    match = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if not match:
        raise ValueError("invalid")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("invalid")
    return hour * 60 + minute


def _parse_time_range_minutes(time_label: str):
    label = (time_label or "").strip()
    if not label:
        return None

    # Remove day prefix if present
    label = re.sub(r"^(M|T|W|TH|F|SAT|SUN|TTH)\s+", "", label, flags=re.IGNORECASE)

    # Normalize various dash characters
    normalized = (
        label.replace("—", "-")
        .replace("–", "-")
        .replace("−", "-")
    )

    # Try format: "480-600" (minutes from midnight)
    match = re.match(r"^(\d+)\s*-\s*(\d+)$", normalized)
    if match:
        try:
            start_min = int(match.group(1))
            end_min = int(match.group(2))
            if end_min > start_min:
                return start_min, end_min
        except Exception:
            pass

    # Try format: "08:00:00-10:00:00" or "8:00:00-10:00:00" (HH:MM:SS with seconds)
    match = re.match(r"(\d{1,2}):(\d{2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2}):(\d{2})", normalized)
    if match:
        try:
            start_h, start_m = int(match.group(1)), int(match.group(2))
            end_h, end_m = int(match.group(4)), int(match.group(5))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            if end_min > start_min:
                return start_min, end_min
        except Exception:
            pass

    # Try format: "08:00-10:00" or "8:00-10:00" (HH:MM)
    parts = [p.strip() for p in normalized.split("-") if p.strip()]
    if len(parts) == 2:
        try:
            # Handle HH:MM:SS by stripping seconds
            part1 = re.sub(r":\d{2}$", "", parts[0]) if parts[0].count(":") > 1 else parts[0]
            part2 = re.sub(r":\d{2}$", "", parts[1]) if parts[1].count(":") > 1 else parts[1]
            start_min = _time_str_to_minutes(part1)
            end_min = _time_str_to_minutes(part2)
            if end_min > start_min:
                return start_min, end_min
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# College routes
# ---------------------------------------------------------------------------
@entities_bp.route("/colleges", methods=["GET"])
def list_colleges():
    with _get_session() as db:
        colleges = db.query(models.College).all()
        return jsonify(_serialize_list(colleges, schemas.CollegeResponse))


@entities_bp.route("/colleges", methods=["POST"])
def create_college():
    payload = request.get_json(force=True) or {}
    try:
        college = schemas.CollegeCreate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        db_college = models.College(**college.model_dump())
        db.add(db_college)
        db.commit()
        db.refresh(db_college)
        return jsonify(_serialize(db_college, schemas.CollegeResponse)), 201


@entities_bp.route("/colleges/<int:college_id>", methods=["GET"])
def get_college(college_id: int):
    with _get_session() as db:
        college = db.query(models.College).filter(models.College.id == college_id).first()
        if not college:
            return jsonify({"detail": "College not found"}), 404
        return jsonify(_serialize(college, schemas.CollegeResponse))


@entities_bp.route("/colleges/<int:college_id>", methods=["PUT"])
def update_college(college_id: int):
    payload = request.get_json(force=True) or {}
    try:
        update_data = schemas.CollegeUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        college = db.query(models.College).filter(models.College.id == college_id).first()
        if not college:
            return jsonify({"detail": "College not found"}), 404

        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(college, key, value)

        db.commit()
        db.refresh(college)
        return jsonify(_serialize(college, schemas.CollegeResponse))


@entities_bp.route("/colleges/<int:college_id>", methods=["DELETE"])
def delete_college(college_id: int):
    with _get_session() as db:
        college = db.query(models.College).filter(models.College.id == college_id).first()
        if not college:
            return jsonify({"detail": "College not found"}), 404
        db.delete(college)
        db.commit()
        return "", 204


# ---------------------------------------------------------------------------
# Course routes
# ---------------------------------------------------------------------------
@entities_bp.route("/courses", methods=["GET"])
def list_courses():
    with _get_session() as db:
        courses = db.query(models.Course).all()
        return jsonify(_serialize_list(courses, schemas.CourseResponse))


@entities_bp.route("/courses", methods=["POST"])
def create_course():
    payload = request.get_json(force=True) or {}
    try:
        course = schemas.CourseCreate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        db_course = models.Course(**course.model_dump())
        db.add(db_course)
        db.commit()
        db.refresh(db_course)
        return jsonify(_serialize(db_course, schemas.CourseResponse)), 201


@entities_bp.route("/courses/<int:course_id>", methods=["GET"])
def get_course(course_id: int):
    with _get_session() as db:
        course = db.query(models.Course).filter(models.Course.id == course_id).first()
        if not course:
            return jsonify({"detail": "Course not found"}), 404
        return jsonify(_serialize(course, schemas.CourseResponse))


@entities_bp.route("/courses/<int:course_id>", methods=["PUT"])
def update_course(course_id: int):
    payload = request.get_json(force=True) or {}
    try:
        course_update = schemas.CourseUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        course = db.query(models.Course).filter(models.Course.id == course_id).first()
        if not course:
            return jsonify({"detail": "Course not found"}), 404

        for key, value in course_update.model_dump(exclude_unset=True).items():
            setattr(course, key, value)

        db.commit()
        db.refresh(course)
        return jsonify(_serialize(course, schemas.CourseResponse))


@entities_bp.route("/courses/<int:course_id>", methods=["DELETE"])
def delete_course(course_id: int):
    with _get_session() as db:
        course = db.query(models.Course).filter(models.Course.id == course_id).first()
        if not course:
            return jsonify({"detail": "Course not found"}), 404
        db.delete(course)
        db.commit()
        return "", 204


# ---------------------------------------------------------------------------
# Instructor routes
# ---------------------------------------------------------------------------
@entities_bp.route("/instructors", methods=["GET"])
def list_instructors():
    """List all instructors."""
    logger.info("Fetching all instructors")
    try:
        with _get_session() as db:
            instructors = db.query(models.Instructor).all()
            logger.info(f"Found {len(instructors)} instructors")
            return jsonify(_serialize_list(instructors, schemas.InstructorResponse))
    except Exception as e:
        logger.error(f"Error listing instructors: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to retrieve instructors", "details": str(e)}), 500


@entities_bp.route("/instructors", methods=["POST"])
def create_instructor():
    """Create a new instructor."""
    logger.info("Creating new instructor")
    data = request.get_json()
    if not data:
        logger.warning("No input data provided")
        return jsonify({"error": "No input data provided"}), 400
    
    try:
        # Validate input data
        instructor_data = schemas.InstructorCreate(**data)
    except ValidationError as err:
        logger.warning(f"Validation error: {err.errors()}")
        return jsonify({"error": "Validation error", "details": err.errors()}), 400

    try:
        with _get_session() as db:
            # Derive a base username from first and last name if none is provided.
            first = (instructor_data.first_name or "").strip()
            last = (instructor_data.last_name or "").strip()
            # Optional override from payload, otherwise use "firstname.lastname" style.
            base_username = (instructor_data.username or f"{first} {last}").strip()
            # Normalize: lowercase and replace spaces with dots
            base_username = base_username.lower().replace(" ", ".")

            # Ensure username is unique across users; add numeric suffix if needed.
            candidate = base_username or "instructor"
            suffix = 1
            while (
                db.query(models.User)
                .filter(models.User.username == candidate)
                .first()
            ) is not None:
                suffix += 1
                candidate = f"{base_username}{suffix}"

            # Prepare instructor payload (exclude password, which belongs to User)
            instructor_payload = instructor_data.model_dump(exclude={"password", "username"})
            instructor_payload["username"] = candidate

            # Create new instructor
            db_instructor = models.Instructor(**instructor_payload)
            db.add(db_instructor)
            db.flush()  # Assign ID without committing yet

            # Always create a linked User account with default credentials.
            # Default username: derived candidate above
            # Default password: instructor's last name (as provided)
            default_password = last or first or candidate
            password_hash = hashlib.sha256(default_password.encode()).hexdigest()

            db_user = models.User(
                username=candidate,
                password_hash=password_hash,
                role="instructor",
                instructor_id=db_instructor.id,
            )
            db.add(db_user)

            db.commit()
            db.refresh(db_instructor)
            logger.info(
                "Created instructor with ID: %s and default login username=%s password=<last_name>",
                db_instructor.id,
                candidate,
            )
            return jsonify(_serialize(db_instructor, schemas.InstructorResponse)), 201
    except Exception as e:
        logger.error(f"Error creating instructor: {e}", exc_info=True)

@entities_bp.route("/instructors/<int:instructor_id>", methods=["GET"])
def get_instructor(instructor_id: int):
    """Get a specific instructor by ID."""
    logger.info(f"Fetching instructor with ID: {instructor_id}")
    try:
        with _get_session() as db:
            instructor = db.query(models.Instructor).get(instructor_id)
            if not instructor:
                logger.warning(f"Instructor with ID {instructor_id} not found")
                return jsonify({"error": "Instructor not found"}), 404
            return jsonify(_serialize(instructor, schemas.InstructorResponse))
    except Exception as e:
        logger.error(f"Error fetching instructor {instructor_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to retrieve instructor", "details": str(e)}), 500


@entities_bp.route("/instructors/<int:instructor_id>", methods=["PUT"])
def update_instructor(instructor_id: int):
    payload = request.get_json(force=True) or {}
    try:
        instructor_update = schemas.InstructorUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        instructor = (
            db.query(models.Instructor)
            .filter(models.Instructor.id == instructor_id)
            .first()
        )
        if not instructor:
            return jsonify({"detail": "Instructor not found"}), 404

        data = instructor_update.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(instructor, key, value)

        # If the client did NOT explicitly provide assignable_courses,
        # keep the existing behavior of auto-populating specialization
        # from the instructor's college. When assignable_courses is
        # present, we respect it as a manual specialization list.
        has_assignable_courses = "assignable_courses" in data
        if not has_assignable_courses:
            college_id = data.get("college_id", instructor.college_id)
            if college_id:
                courses = (
                    db.query(models.Course)
                    .filter(models.Course.college_id == college_id)
                    .all()
                )
                codes = [course.code for course in courses]
                instructor.assignable_courses = ",".join(codes) if codes else None
            elif "college_id" in data and college_id is None:
                instructor.assignable_courses = None

        db.commit()
        db.refresh(instructor)
        return jsonify(_serialize(instructor, schemas.InstructorResponse))


@entities_bp.route("/instructors/<int:instructor_id>/workload", methods=["GET"])
def get_instructor_workload(instructor_id: int):
    semester = request.args.get("semester", type=int)
    if semester not in {1, 2}:
        return jsonify({"detail": "semester query parameter must be 1 or 2"}), 400

    with _get_session() as db:
        instructor = db.query(models.Instructor).get(instructor_id)
        if not instructor:
            return jsonify({"detail": "Instructor not found"}), 404

        schedules = (
            db.query(models.Schedule)
            .filter(
                models.Schedule.instructor_id == instructor_id,
                models.Schedule.semester == semester,
            )
            .all()
        )
        
        # Debug logging
        logger.info(f"Workload query: instructor_id={instructor_id}, semester={semester}, found {len(schedules)} schedules")

        total_minutes = 0
        subject_ids = set()
        for sched in schedules:
            if sched.subject_id:
                subject_ids.add(sched.subject_id)

            if not sched.time:
                continue

            time_label = re.sub(
                r"^(M|T|W|TH|F|SAT|SUN|TTH)\s+",
                "",
                str(sched.time).strip(),
                flags=re.IGNORECASE,
            )

            parsed = _parse_time_range_minutes(time_label)
            if parsed:
                start_min, end_min = parsed
                total_minutes += max(0, end_min - start_min)
                continue
            else:
                # Log unparsed time for debugging
                logger.warning(f"Could not parse time range from: '{sched.time}' (cleaned: '{time_label}')")

            ts = (
                db.query(models.Timeslot)
                .filter(
                    models.Timeslot.label == time_label,
                    models.Timeslot.day == sched.day_id,
                )
                .first()
            )
            if ts is not None:
                total_minutes += max(0, int(ts.end_min) - int(ts.start_min))

        weekly_hours = round(total_minutes / 60.0, 2)

        units_total = 0
        # Build a mapping of subject_id -> units for quick lookup
        if subject_ids:
            subjects = db.query(models.Subject).filter(models.Subject.id.in_(sorted(subject_ids))).all()
            subject_units_map = {s.id: int(s.unit or 0) for s in subjects}
            
            # Count units for each schedule entry (each class/block counts its units)
            for sched in schedules:
                if sched.subject_id and sched.subject_id in subject_units_map:
                    units_total += subject_units_map[sched.subject_id]
            
            logger.info(f"Units calculation: {len(schedules)} schedule entries, {len(subjects)} unique subjects, total={units_total}")

        employment_type = (getattr(instructor, "employment_type", None) or "regular").strip().lower()
        designation = (getattr(instructor, "designation", None) or "").strip()

        deductions = {
            "program chair": 3,
            "college secretary": 3,
            "dean": 12,
            "associate dean": 12,
            "director": 12,
        }

        if employment_type == "visiting":
            limit_hours = 30
        else:
            deduction = deductions.get(designation.strip().lower(), 0) if designation else 0
            limit_hours = max(0, 24 - deduction)

        overload_hours = round(max(0.0, weekly_hours - float(limit_hours)), 2)
        overload_pay_hours = round(max(0.0, weekly_hours - 30.0), 2)

        warnings = []
        if designation and weekly_hours > float(limit_hours):
            warnings.append(
                "CHED guidance: faculty with a designation should not take overload; if unavoidable, a letter to the VPAA may be required."
            )
        if employment_type == "visiting" and weekly_hours > 30:
            warnings.append("Visiting lecturer load exceeds 30 hours/week.")
        if employment_type != "visiting" and not designation and weekly_hours > 30:
            warnings.append("Overload pay threshold reached: hours beyond 30 may be eligible for overload pay.")

        return jsonify(
            {
                "instructor_id": instructor_id,
                "semester": semester,
                "employment_type": employment_type,
                "designation": designation or None,
                "weekly_hours": weekly_hours,
                "limit_hours": limit_hours,
                "overload_hours": overload_hours,
                "overload_pay_hours": overload_pay_hours,
                "units_total": units_total,
                "schedule_count": len(schedules),
                "warnings": warnings,
            }
        )


@entities_bp.route("/instructors/<int:instructor_id>", methods=["DELETE"])
def delete_instructor(instructor_id: int):
	try:
		with _get_session() as db:
			instructor = (
				db.query(models.Instructor)
				.filter(models.Instructor.id == instructor_id)
				.first()
			)
			if not instructor:
				return jsonify({"detail": "Instructor not found"}), 404

			# Prevent deleting instructors that still have schedules to
			# avoid orphaning schedule records.
			if instructor.schedules:
				return (
					jsonify({"detail": "Cannot delete instructor with existing schedules"}),
					400,
				)

			# Delete linked User account, if any, so credentials are also removed.
			user = (
				db.query(models.User)
				.filter(models.User.instructor_id == instructor_id)
				.first()
			)
			if user:
				db.delete(user)

			db.delete(instructor)
			db.commit()
			return "", 204
	except SQLAlchemyError as e:
		logger.error(
			f"Database error deleting instructor {instructor_id}: {e}", exc_info=True
		)
		return jsonify({"detail": "Database error occurred"}), 500
	except Exception as e:
		logger.error(
			f"Error deleting instructor {instructor_id}: {e}", exc_info=True
		)
		return jsonify({"detail": str(e)}), 500


# ---------------------------------------------------------------------------
# Day routes
# ---------------------------------------------------------------------------
@entities_bp.route("/days", methods=["GET"])
def list_days():
    with _get_session() as db:
        days = db.query(models.Day).all()
        return jsonify(_serialize_list(days, schemas.DayResponse))


@entities_bp.route("/days", methods=["POST"])
def create_day():
    payload = request.get_json(force=True) or {}
    try:
        day = schemas.DayCreate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        db_day = models.Day(**day.model_dump())
        db.add(db_day)
        db.commit()
        db.refresh(db_day)
        return jsonify(_serialize(db_day, schemas.DayResponse)), 201


@entities_bp.route("/days/<int:day_id>", methods=["GET"])
def get_day(day_id: int):
    with _get_session() as db:
        day = db.query(models.Day).filter(models.Day.id == day_id).first()
        if not day:
            return jsonify({"detail": "Day not found"}), 404
        return jsonify(_serialize(day, schemas.DayResponse))


@entities_bp.route("/days/<int:day_id>", methods=["DELETE"])
def delete_day(day_id: int):
    with _get_session() as db:
        day = db.query(models.Day).filter(models.Day.id == day_id).first()
        if not day:
            return jsonify({"detail": "Day not found"}), 404
        db.delete(day)
        db.commit()
        return "", 204


# ---------------------------------------------------------------------------
# Subject routes
# ---------------------------------------------------------------------------
@entities_bp.route("/subjects", methods=["GET"])
def list_subjects():
    with _get_session() as db:
        subjects = db.query(models.Subject).all()
        return jsonify(_serialize_list(subjects, schemas.SubjectResponse))


@entities_bp.route("/subjects", methods=["POST"])
def create_subject():
    payload = request.get_json(force=True) or {}
    try:
        subject = schemas.SubjectCreate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    if subject.type not in {"LEC", "LAB"}:
        return jsonify({"detail": "Type must be 'LEC' or 'LAB'"}), 400

    if subject.is_major is None:
        return jsonify({"detail": "Subject priority is required (set is_major to true for Major or false for Minor)"}), 400

    if subject.year_level not in {1, 2, 3, 4}:
        return jsonify({"detail": "year_level must be 1, 2, 3, or 4"}), 400

    if subject.semester not in {1, 2}:
        return jsonify({"detail": "semester must be 1 or 2"}), 400

    with _get_session() as db:
        db_subject = models.Subject(**subject.model_dump())
        db.add(db_subject)
        db.commit()
        db.refresh(db_subject)
        return jsonify(_serialize(db_subject, schemas.SubjectResponse)), 201


@entities_bp.route("/subjects/<int:subject_id>", methods=["GET"])
def get_subject(subject_id: int):
    with _get_session() as db:
        subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
        if not subject:
            return jsonify({"detail": "Subject not found"}), 404
        return jsonify(_serialize(subject, schemas.SubjectResponse))


@entities_bp.route("/subjects/<int:subject_id>", methods=["PUT"])
def update_subject(subject_id: int):
    payload = request.get_json(force=True) or {}
    try:
        subject_update = schemas.SubjectUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        subject = (
            db.query(models.Subject)
            .filter(models.Subject.id == subject_id)
            .first()
        )
        if not subject:
            return jsonify({"detail": "Subject not found"}), 404

        for key, value in subject_update.model_dump(exclude_unset=True).items():
            if key == "type" and value not in {"LEC", "LAB"}:
                return jsonify({"detail": "Type must be 'LEC' or 'LAB'"}), 400
            if key == "year_level" and value is not None and value not in {1, 2, 3, 4}:
                return jsonify({"detail": "year_level must be 1, 2, 3, or 4"}), 400
            if key == "semester" and value is not None and value not in {1, 2}:
                return jsonify({"detail": "semester must be 1 or 2"}), 400
            setattr(subject, key, value)

        db.commit()
        db.refresh(subject)
        return jsonify(_serialize(subject, schemas.SubjectResponse))


@entities_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
def delete_subject(subject_id: int):
    with _get_session() as db:
        subject = (
            db.query(models.Subject)
            .filter(models.Subject.id == subject_id)
            .first()
        )
        if not subject:
            return jsonify({"detail": "Subject not found"}), 404
        db.delete(subject)
        db.commit()
        return "", 204


# ---------------------------------------------------------------------------
# Room routes
# ---------------------------------------------------------------------------
@entities_bp.route("/rooms", methods=["GET"])
def list_rooms():
    with _get_session() as db:
        rooms = db.query(models.Room).all()
        return jsonify(_serialize_list(rooms, schemas.RoomResponse))


@entities_bp.route("/rooms", methods=["POST"])
def create_room():
    payload = request.get_json(force=True) or {}
    try:
        room = schemas.RoomCreate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    if room.type not in {"LEC", "LAB"}:
        return jsonify({"detail": "Type must be 'LEC' or 'LAB'"}), 400

    with _get_session() as db:
        db_room = models.Room(**room.model_dump())
        db.add(db_room)
        db.commit()
        db.refresh(db_room)
        return jsonify(_serialize(db_room, schemas.RoomResponse)), 201


@entities_bp.route("/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id: int):
    with _get_session() as db:
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        if not room:
            return jsonify({"detail": "Room not found"}), 404
        return jsonify(_serialize(room, schemas.RoomResponse))


@entities_bp.route("/rooms/<int:room_id>", methods=["PUT"])
def update_room(room_id: int):
    payload = request.get_json(force=True) or {}
    try:
        room_update = schemas.RoomUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        if not room:
            return jsonify({"detail": "Room not found"}), 404

        for key, value in room_update.model_dump(exclude_unset=True).items():
            if key == "type" and value not in {"LEC", "LAB"}:
                return jsonify({"detail": "Type must be 'LEC' or 'LAB'"}), 400
            setattr(room, key, value)

        db.commit()
        db.refresh(room)
        return jsonify(_serialize(room, schemas.RoomResponse))


@entities_bp.route("/rooms/<int:room_id>", methods=["DELETE"])
def delete_room(room_id: int):
    with _get_session() as db:
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        if not room:
            return jsonify({"detail": "Room not found"}), 404
        db.delete(room)
        db.commit()
        return "", 204

