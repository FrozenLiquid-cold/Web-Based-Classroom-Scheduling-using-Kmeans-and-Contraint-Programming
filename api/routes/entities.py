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


def _parse_12h_to_minutes(value: str) -> int:
    """Parse '7:00 AM' or '1:30 PM' into minutes from midnight."""
    value = (value or "").strip().upper()
    match = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)$", value)
    if not match:
        raise ValueError(f"Cannot parse 12h time: {value}")
    hour = int(match.group(1))
    minute = int(match.group(2))
    period = match.group(3)
    if hour == 12:
        hour = 0 if period == "AM" else 12
    elif period == "PM":
        hour += 12
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

    # Try format: "7:00 AM - 8:30 AM" (12-hour with AM/PM)
    match_12h = re.match(
        r"(\d{1,2}:\d{2}\s*[AaPp][Mm])\s*-\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])",
        normalized,
    )
    if match_12h:
        try:
            start_min = _parse_12h_to_minutes(match_12h.group(1))
            end_min = _parse_12h_to_minutes(match_12h.group(2))
            if end_min > start_min:
                return start_min, end_min
        except Exception:
            pass

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
    """Create a new instructor (without auto-creating a user account)."""
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
            # Prepare instructor payload (exclude password and username since accounts are managed separately)
            instructor_payload = instructor_data.model_dump(exclude={"password", "username"})

            # Create new instructor
            db_instructor = models.Instructor(**instructor_payload)
            db.add(db_instructor)
            db.commit()
            db.refresh(db_instructor)
            logger.info(
                "Created instructor with ID: %s (no auto-account created)",
                db_instructor.id,
            )
            return jsonify(_serialize(db_instructor, schemas.InstructorResponse)), 201
    except Exception as e:
        logger.error(f"Error creating instructor: {e}", exc_info=True)
        return jsonify({"error": "Failed to create instructor", "details": str(e)}), 500

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

        # Auto-populate specialization from the instructor's college ONLY
        # when the college_id was explicitly changed AND assignable_courses
        # was not explicitly provided. This prevents overwrites when
        # toggling is_active or other fields.
        has_assignable_courses = "assignable_courses" in data
        college_id_changed = "college_id" in data
        if not has_assignable_courses and college_id_changed:
            college_id = data.get("college_id")
            if college_id:
                courses = (
                    db.query(models.Course)
                    .filter(models.Course.college_id == college_id)
                    .all()
                )
                codes = [course.code for course in courses]
                instructor.assignable_courses = ",".join(codes) if codes else None
            else:
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
            
            # Count units per unique (subject, block) combination
            # Each distinct class (same subject taught to different blocks) counts separately,
            # but multiple day-entries for the same class should NOT multiply units.
            seen_subject_blocks = set()
            for sched in schedules:
                if sched.subject_id and sched.subject_id in subject_units_map:
                    block_key = (sched.subject_id, getattr(sched, 'block', None) or '')
                    if block_key not in seen_subject_blocks:
                        seen_subject_blocks.add(block_key)
                        units_total += subject_units_map[sched.subject_id]
            
            logger.info(f"Units calculation: {len(schedules)} schedule entries, {len(seen_subject_blocks)} unique subject-blocks, {len(subjects)} unique subjects, total={units_total}")

        employment_type = (getattr(instructor, "employment_type", None) or "regular").strip().lower()
        designation = (getattr(instructor, "designation", None) or "").strip()

        from ..scheduler.deductions import get_deduction_map
        deductions = get_deduction_map(db)

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
                "schedule_count": len(seen_subject_blocks) if subject_ids else 0,
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
# User account routes (Admin-managed)
# ---------------------------------------------------------------------------
@entities_bp.route("/users", methods=["GET"])
def list_users():
    """List all user accounts, enriched with instructor name if linked."""
    with _get_session() as db:
        users = db.query(models.User).all()
        result = []
        for u in users:
            row = {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "instructor_id": u.instructor_id,
                "instructor_name": None,
            }
            if u.instructor_id:
                instr = db.query(models.Instructor).get(u.instructor_id)
                if instr:
                    parts = [instr.first_name or ""]
                    if instr.middle_name:
                        parts.append(instr.middle_name)
                    parts.append(instr.last_name or "")
                    row["instructor_name"] = " ".join(p for p in parts if p)
            result.append(row)
        return jsonify(result)


@entities_bp.route("/users", methods=["POST"])
def create_user():
    """Create a new user account."""
    payload = request.get_json(force=True) or {}
    try:
        user_data = schemas.UserCreate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    if user_data.role not in {"admin", "registrar", "instructor"}:
        return jsonify({"detail": "Role must be 'admin', 'registrar', or 'instructor'"}), 400

    with _get_session() as db:
        # Ensure username is unique
        existing = db.query(models.User).filter(models.User.username == user_data.username).first()
        if existing:
            return jsonify({"detail": "Username already exists"}), 400

        # If instructor role, validate instructor_id
        if user_data.role == "instructor":
            if not user_data.instructor_id:
                return jsonify({"detail": "instructor_id is required for instructor accounts"}), 400
            instr = db.query(models.Instructor).get(user_data.instructor_id)
            if not instr:
                return jsonify({"detail": "Instructor not found"}), 404
            # Check no account already linked to this instructor
            existing_link = db.query(models.User).filter(models.User.instructor_id == user_data.instructor_id).first()
            if existing_link:
                return jsonify({"detail": "This instructor already has a linked account"}), 400

        password_hash = hashlib.sha256(user_data.password.encode()).hexdigest()
        db_user = models.User(
            username=user_data.username,
            password_hash=password_hash,
            role=user_data.role,
            instructor_id=user_data.instructor_id if user_data.role == "instructor" else None,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return jsonify(_serialize(db_user, schemas.UserResponse)), 201


@entities_bp.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id: int):
    """Update an existing user account."""
    payload = request.get_json(force=True) or {}
    try:
        user_update = schemas.UserUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return jsonify({"detail": "User not found"}), 404

        data = user_update.model_dump(exclude_unset=True)

        if "username" in data and data["username"]:
            existing = db.query(models.User).filter(
                models.User.username == data["username"],
                models.User.id != user_id,
            ).first()
            if existing:
                return jsonify({"detail": "Username already exists"}), 400
            user.username = data["username"]

        if "password" in data and data["password"]:
            user.password_hash = hashlib.sha256(data["password"].encode()).hexdigest()

        if "role" in data and data["role"]:
            if data["role"] not in {"admin", "registrar", "instructor"}:
                return jsonify({"detail": "Invalid role"}), 400
            user.role = data["role"]

        if "instructor_id" in data:
            user.instructor_id = data["instructor_id"]

        db.commit()
        db.refresh(user)
        return jsonify(_serialize(user, schemas.UserResponse))


@entities_bp.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id: int):
    """Delete a user account."""
    with _get_session() as db:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return jsonify({"detail": "User not found"}), 404
        db.delete(user)
        db.commit()
        return "", 204


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

        # Auto-create default time blocks for the new day
        _seed_default_time_blocks_for_day(db, db_day.id)

        return jsonify(_serialize(db_day, schemas.DayResponse)), 201


@entities_bp.route("/days/<int:day_id>", methods=["GET"])
def get_day(day_id: int):
    with _get_session() as db:
        day = db.query(models.Day).filter(models.Day.id == day_id).first()
        if not day:
            return jsonify({"detail": "Day not found"}), 404
        return jsonify(_serialize(day, schemas.DayResponse))


@entities_bp.route("/days/<int:day_id>", methods=["PUT"])
def update_day(day_id: int):
    payload = request.get_json(force=True) or {}
    try:
        day_update = schemas.DayUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    with _get_session() as db:
        day = db.query(models.Day).filter(models.Day.id == day_id).first()
        if not day:
            return jsonify({"detail": "Day not found"}), 404

        data = day_update.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(day, key, value)

        db.commit()
        db.refresh(day)
        return jsonify(_serialize(day, schemas.DayResponse))


@entities_bp.route("/days/<int:day_id>", methods=["DELETE"])
def delete_day(day_id: int):
    with _get_session() as db:
        day = db.query(models.Day).filter(models.Day.id == day_id).first()
        if not day:
            return jsonify({"detail": "Day not found"}), 404
        # Auto-delete associated time blocks first
        db.query(models.TimeBlock).filter(models.TimeBlock.day_id == day_id).delete()
        db.delete(day)
        db.commit()
        return "", 204


def _seed_default_time_blocks_for_day(db, day_id: int):
    """Create the 14 default registrar time windows for a single day.

    Called automatically when a new Day is created via the API so that
    it is immediately schedulable without manual time-block setup.
    """
    # The original 14 registrar windows  (start, end, is_lab)
    registrar_windows = [
        ("07:30", "08:30", False),
        ("09:00", "10:00", False),
        ("10:30", "11:30", False),
        ("07:30", "09:00", True),
        ("09:00", "10:30", True),
        ("10:30", "12:00", True),
        ("13:00", "14:00", False),
        ("14:30", "15:30", False),
        ("16:00", "17:00", False),
        ("13:00", "14:30", True),
        ("14:30", "16:00", True),
        ("16:00", "17:30", True),
        ("17:30", "19:00", False),
        ("08:00", "11:00", False),  # NSTP
    ]

    # Find the max block_id to auto-increment
    max_bid = db.query(models.TimeBlock.block_id).order_by(models.TimeBlock.block_id.desc()).first()
    next_bid = (max_bid[0] + 1) if max_bid else 1

    for start, end, is_lab in registrar_windows:
        s_min = _time_str_to_minutes(start)
        e_min = _time_str_to_minutes(end)
        tb = models.TimeBlock(
            block_id=next_bid,
            day_id=day_id,
            label=_format_time_label(start, end),
            start_time=start,
            end_time=end,
            start_min=s_min,
            end_min=e_min,
            is_lab=is_lab,
        )
        db.add(tb)
        next_bid += 1

    db.commit()
    logger.info("Auto-created 14 default time blocks for day_id=%s", day_id)


# ---------------------------------------------------------------------------
# Subject routes
# ---------------------------------------------------------------------------

def _serialize_subject(subject):
    """Serialize a Subject model to dict including preferred_room_ids."""
    data = _serialize(subject, schemas.SubjectResponse)
    data["preferred_room_ids"] = [
        pref.room_id for pref in (subject.preferred_rooms or [])
    ]
    return data


def _sync_subject_room_prefs(db, subject_id, room_ids):
    """Replace all room preferences for a subject with the given room_ids."""
    # Delete existing preferences
    db.query(models.SubjectRoomPreference).filter(
        models.SubjectRoomPreference.subject_id == subject_id
    ).delete()
    # Insert new ones
    if room_ids:
        for rid in room_ids:
            db.add(models.SubjectRoomPreference(
                subject_id=subject_id,
                room_id=rid,
            ))


@entities_bp.route("/subjects", methods=["GET"])
def list_subjects():
    with _get_session() as db:
        subjects = db.query(models.Subject).all()
        return jsonify([_serialize_subject(s) for s in subjects])


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
        # Separate preferred_room_ids from core subject fields
        subject_data = subject.model_dump(exclude={"preferred_room_ids"})
        db_subject = models.Subject(**subject_data)
        db.add(db_subject)
        db.flush()  # Get the ID before adding preferences

        # Save room preferences
        if subject.preferred_room_ids:
            _sync_subject_room_prefs(db, db_subject.id, subject.preferred_room_ids)

        db.commit()
        db.refresh(db_subject)
        return jsonify(_serialize_subject(db_subject)), 201


@entities_bp.route("/subjects/<int:subject_id>", methods=["GET"])
def get_subject(subject_id: int):
    with _get_session() as db:
        subject = db.query(models.Subject).filter(models.Subject.id == subject_id).first()
        if not subject:
            return jsonify({"detail": "Subject not found"}), 404
        return jsonify(_serialize_subject(subject))


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

        update_data = subject_update.model_dump(exclude_unset=True)
        room_ids = update_data.pop("preferred_room_ids", None)

        for key, value in update_data.items():
            if key == "type" and value not in {"LEC", "LAB"}:
                return jsonify({"detail": "Type must be 'LEC' or 'LAB'"}), 400
            if key == "year_level" and value is not None and value not in {1, 2, 3, 4}:
                return jsonify({"detail": "year_level must be 1, 2, 3, or 4"}), 400
            if key == "semester" and value is not None and value not in {1, 2}:
                return jsonify({"detail": "semester must be 1 or 2"}), 400
            setattr(subject, key, value)

        # Sync room preferences if provided
        if room_ids is not None:
            _sync_subject_room_prefs(db, subject_id, room_ids)

        db.commit()
        db.refresh(subject)
        return jsonify(_serialize_subject(subject))


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


@entities_bp.route("/subjects/scheduled-ids", methods=["GET"])
def get_scheduled_subject_ids():
    """Return a list of subject IDs that have at least one schedule entry."""
    semester = request.args.get("semester", type=int)
    with _get_session() as db:
        query = db.query(models.Schedule.subject_id).distinct()
        if semester:
            query = query.filter(models.Schedule.semester == semester)
        ids = [row[0] for row in query.all() if row[0] is not None]
        return jsonify(ids)


@entities_bp.route("/subjects/merge/preview", methods=["POST"])
def merge_preview():
    """Preview a merge: return schedule details for both subjects + conflict analysis."""
    payload = request.get_json(force=True) or {}
    source_id = payload.get("source_id")
    target_id = payload.get("target_id")

    if not source_id or not target_id:
        return jsonify({"detail": "source_id and target_id are required"}), 400
    if source_id == target_id:
        return jsonify({"detail": "Source and target must be different"}), 400

    with _get_session() as db:
        source = db.query(models.Subject).filter(models.Subject.id == source_id).first()
        target = db.query(models.Subject).filter(models.Subject.id == target_id).first()
        if not source:
            return jsonify({"detail": "Source subject not found"}), 404
        if not target:
            return jsonify({"detail": "Target subject not found"}), 404

        def _sched_to_dict(s):
            instr = None
            if s.instructor_id:
                i = db.query(models.Instructor).get(s.instructor_id)
                if i:
                    instr = {"id": i.id, "name": f"{i.first_name or ''} {i.last_name or ''}".strip()}
            room = None
            if s.room_id:
                r = db.query(models.Room).get(s.room_id)
                if r:
                    room = {"id": r.id, "name": r.name}
            day = None
            if s.day_id:
                d = db.query(models.Day).get(s.day_id)
                if d:
                    day = {"id": d.id, "label": d.label}
            return {
                "id": s.id,
                "instructor": instr,
                "room": room,
                "day": day,
                "time": s.time,
                "block": s.block,
                "year": s.year,
                "semester": s.semester,
            }

        source_schedules = db.query(models.Schedule).filter(models.Schedule.subject_id == source_id).all()
        target_schedules = db.query(models.Schedule).filter(models.Schedule.subject_id == target_id).all()

        source_list = [_sched_to_dict(s) for s in source_schedules]
        target_list = [_sched_to_dict(s) for s in target_schedules]

        # Detect conflicts: instructor or room double-booking (only for selected blocks if provided)
        selected_blocks = payload.get("selected_blocks")
        resource_picks = payload.get("resource_picks") or {}
        sel = set(selected_blocks) if selected_blocks else None

        def _is_sel_preview(side, sched):
            if sel is None:
                return True  # No selection filter = check all
            bk = sched.block or '_none'
            return f"{side}_{bk}" in sel

        def _resource_survives(side, sched, res_type):
            """Check if the resource type survives on this block after picks are applied."""
            if not resource_picks:
                return True  # No picks yet = assume everything survives
            bk = sched.block or '_none'
            dec_key = f"{side}_{bk}"
            pick = resource_picks.get(res_type)
            if not pick:
                return True  # No pick for this type = assume survives
            return pick == dec_key

        conflicts = []
        for ss in source_schedules:
            if not _is_sel_preview('source', ss):
                continue
            for ts in target_schedules:
                if not _is_sel_preview('target', ts):
                    continue
                if ss.day_id and ts.day_id and ss.day_id == ts.day_id and ss.time and ts.time and ss.time == ts.time:
                    # Only flag instructor conflict if instructor survives on BOTH blocks
                    if (ss.instructor_id and ts.instructor_id and ss.instructor_id == ts.instructor_id
                            and _resource_survives('source', ss, 'instructor')
                            and _resource_survives('target', ts, 'instructor')):
                        instr = db.query(models.Instructor).get(ss.instructor_id)
                        name = f"{instr.first_name} {instr.last_name}" if instr else f"ID {ss.instructor_id}"
                        conflicts.append({
                            "type": "instructor",
                            "message": f"Instructor {name} is double-booked on day {ss.day_id} at {ss.time}"
                        })
                    # Only flag room conflict if room survives on BOTH blocks
                    if (ss.room_id and ts.room_id and ss.room_id == ts.room_id
                            and _resource_survives('source', ss, 'room')
                            and _resource_survives('target', ts, 'room')):
                        room = db.query(models.Room).get(ss.room_id)
                        rname = room.name if room else f"ID {ss.room_id}"
                        conflicts.append({
                            "type": "room",
                            "message": f"Room {rname} is double-booked on day {ss.day_id} at {ss.time}"
                        })
        # --- Global conflict check: picked resources vs ALL other schedules ---
        global_conflicts = []
        if resource_picks and sel:
            from api.routes.validation import parse_time, _parse_schedule_time, times_overlap
            from sqlalchemy.orm import joinedload as jl

            # Group schedules by block key to extract winning values
            all_by_key = {}
            for s in source_schedules:
                key = f"source_{s.block or '_none'}"
                all_by_key.setdefault(key, []).append(s)
            for s in target_schedules:
                key = f"target_{s.block or '_none'}"
                all_by_key.setdefault(key, []).append(s)

            win_instr_id = None
            if resource_picks.get('instructor') and resource_picks['instructor'] in all_by_key:
                win_instr_id = all_by_key[resource_picks['instructor']][0].instructor_id

            win_room_id = None
            if resource_picks.get('room') and resource_picks['room'] in all_by_key:
                win_room_id = all_by_key[resource_picks['room']][0].room_id

            win_time_entries = []
            if resource_picks.get('time') and resource_picks['time'] in all_by_key:
                win_time_entries = [(s.day_id, s.time) for s in all_by_key[resource_picks['time']]]

            # IDs to exclude (source + target subjects)
            exclude_subj_ids = [source_id, target_id]

            all_days_map = {d.id: d.label for d in db.query(models.Day).all()}
            DAY_NAMES = {"M": "Monday", "T": "Tuesday", "W": "Wednesday", "TH": "Thursday", "F": "Friday"}

            for day_id, time_str in win_time_entries:
                if not day_id or not time_str:
                    continue
                t_start, t_end = _parse_schedule_time(time_str)
                if not t_start or not t_end:
                    continue

                day_label = all_days_map.get(day_id, str(day_id))
                day_full = DAY_NAMES.get(day_label, day_label)

                # Check room conflicts
                if win_room_id:
                    room_hits = db.query(models.Schedule).filter(
                        models.Schedule.day_id == day_id,
                        models.Schedule.room_id == win_room_id,
                        ~models.Schedule.subject_id.in_(exclude_subj_ids)
                    ).options(jl(models.Schedule.subject), jl(models.Schedule.course)).all()

                    for hit in room_hits:
                        h_start, h_end = _parse_schedule_time(hit.time)
                        if times_overlap(t_start, t_end, h_start, h_end):
                            subj_code = hit.subject.code if hit.subject else f"ID {hit.subject_id}"
                            course_code = hit.course.code if hit.course else ""
                            desc = f"{course_code} - {subj_code}" if course_code else subj_code
                            room_name = db.query(models.Room).get(win_room_id).name if win_room_id else "?"
                            global_conflicts.append({
                                "type": "room",
                                "message": f"Room Conflict ({day_full}): {room_name} occupied by {desc} ({hit.time})"
                            })

                # Check instructor conflicts
                if win_instr_id:
                    instr_hits = db.query(models.Schedule).filter(
                        models.Schedule.day_id == day_id,
                        models.Schedule.instructor_id == win_instr_id,
                        ~models.Schedule.subject_id.in_(exclude_subj_ids)
                    ).options(jl(models.Schedule.subject), jl(models.Schedule.course)).all()

                    for hit in instr_hits:
                        h_start, h_end = _parse_schedule_time(hit.time)
                        if times_overlap(t_start, t_end, h_start, h_end):
                            subj_code = hit.subject.code if hit.subject else f"ID {hit.subject_id}"
                            course_code = hit.course.code if hit.course else ""
                            desc = f"{course_code} - {subj_code}" if course_code else subj_code
                            instr = db.query(models.Instructor).get(win_instr_id)
                            instr_name = f"{instr.first_name} {instr.last_name}" if instr else f"ID {win_instr_id}"
                            global_conflicts.append({
                                "type": "instructor",
                                "message": f"Instructor Conflict ({day_full}): {instr_name} teaching {desc} ({hit.time})"
                            })

        all_conflicts = conflicts + global_conflicts

        return jsonify({
            "source": {
                "id": source.id,
                "code": source.code,
                "description": source.description,
                "type": source.type,
                "unit": source.unit,
                "schedules": source_list,
            },
            "target": {
                "id": target.id,
                "code": target.code,
                "description": target.description,
                "type": target.type,
                "unit": target.unit,
                "schedules": target_list,
            },
            "conflicts": all_conflicts,
            "safe": len(all_conflicts) == 0,
        })


@entities_bp.route("/subjects/merge", methods=["POST"])
def merge_subjects():
    payload = request.get_json(force=True) or {}
    try:
        merge_data = schemas.SubjectMerge(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    if merge_data.source_id == merge_data.target_id:
        return jsonify({"detail": "Source and target subjects must be different"}), 400

    with _get_session() as db:
        source_subject = db.query(models.Subject).filter(models.Subject.id == merge_data.source_id).first()
        target_subject = db.query(models.Subject).filter(models.Subject.id == merge_data.target_id).first()

        if not source_subject:
            return jsonify({"detail": "Source subject not found"}), 404
        if not target_subject:
            return jsonify({"detail": "Target subject not found"}), 404

        # --- Conflict detection (block if instructor or room double-booking) ---
        source_schedules = db.query(models.Schedule).filter(
            models.Schedule.subject_id == merge_data.source_id
        ).all()
        target_schedules = db.query(models.Schedule).filter(
            models.Schedule.subject_id == merge_data.target_id
        ).all()

        # Only check conflicts between SELECTED blocks
        selected = set(merge_data.selected_blocks or [])
        def _is_sel(side, sched):
            bk = sched.block or '_none'
            return f"{side}_{bk}" in selected

        conflicts = []
        for ss in source_schedules:
            if not _is_sel('source', ss):
                continue
            for ts in target_schedules:
                if not _is_sel('target', ts):
                    continue
                if ss.day_id and ts.day_id and ss.day_id == ts.day_id and ss.time and ts.time and ss.time == ts.time:
                    if ss.instructor_id and ts.instructor_id and ss.instructor_id == ts.instructor_id:
                        conflicts.append("instructor")
                    if ss.room_id and ts.room_id and ss.room_id == ts.room_id:
                        conflicts.append("room")

        if conflicts:
            return jsonify({
                "detail": "Merge blocked: conflicts detected",
                "conflicts": conflicts,
            }), 409

        # --- Apply cross-block resource picks to selected blocks only ---
        # resource_picks: { "instructor": "source_A", "room": "target_B", "time": "source_A" }
        picks = merge_data.resource_picks or {}
        selected = set(merge_data.selected_blocks or [])
        moved_count = 0

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MERGE] selected_blocks={selected}, picks={picks}")

        # --- Group all schedules by block key ---
        all_by_key = {}
        for s in source_schedules:
            key = f"source_{s.block or '_none'}"
            all_by_key.setdefault(key, []).append(s)
        for s in target_schedules:
            key = f"target_{s.block or '_none'}"
            all_by_key.setdefault(key, []).append(s)

        # --- Extract winning resource values ---
        win_instructor_id = None
        if picks.get('instructor') and picks['instructor'] in all_by_key:
            win_instructor_id = all_by_key[picks['instructor']][0].instructor_id
            logger.info(f"[MERGE] Winning instructor_id={win_instructor_id} from {picks['instructor']}")

        win_room_id = None
        if picks.get('room') and picks['room'] in all_by_key:
            win_room_id = all_by_key[picks['room']][0].room_id
            logger.info(f"[MERGE] Winning room_id={win_room_id} from {picks['room']}")

        win_time_entries = []
        if picks.get('time') and picks['time'] in all_by_key:
            win_time_entries = [(s.day_id, s.time) for s in all_by_key[picks['time']]]
            logger.info(f"[MERGE] Winning time entries={win_time_entries} from {picks['time']}")

        merge_tag = f"[M] {source_subject.code} + {target_subject.code}"

        # --- Apply winning values to all selected blocks ---
        def apply_winning(sched, block_key):
            """Copy winning resource values to this schedule entry."""
            if win_instructor_id is not None:
                sched.instructor_id = win_instructor_id
            if win_room_id is not None:
                sched.room_id = win_room_id
            # For time: match by index within the block
            if win_time_entries:
                block_entries = all_by_key.get(block_key, [])
                idx = block_entries.index(sched) if sched in block_entries else -1
                if 0 <= idx < len(win_time_entries):
                    sched.day_id = win_time_entries[idx][0]
                    sched.time = win_time_entries[idx][1]

        for sched in source_schedules:
            bk = sched.block or '_none'
            key = f"source_{bk}"
            if key in selected:
                logger.info(f"[MERGE] PROCESSING source sched id={sched.id} block={bk} key={key}")
                apply_winning(sched, key)
                sched.subject_id = target_subject.id
                sched.merge_tag = merge_tag
                moved_count += 1
            else:
                logger.info(f"[MERGE] SKIPPING source sched id={sched.id} block={bk} key={key} (not selected)")

        for sched in target_schedules:
            bk = sched.block or '_none'
            key = f"target_{bk}"
            if key in selected:
                logger.info(f"[MERGE] PROCESSING target sched id={sched.id} block={bk} key={key}")
                apply_winning(sched, key)
                sched.merge_tag = merge_tag
            else:
                logger.info(f"[MERGE] SKIPPING target sched id={sched.id} block={bk} key={key} (not selected)")

        # Subjects are NOT modified — merge only affects schedule entries
        # This keeps subjects clean for future semesters
        db.commit()

        return jsonify({
            "detail": "Merge successful",
            "schedules_moved": moved_count,
            "source_subject_code": source_subject.code,
            "target_subject_code": target_subject.code,
        }), 200


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


# ---------------------------------------------------------------------------
# Designation Deductions routes
# ---------------------------------------------------------------------------
@entities_bp.route("/designation-deductions", methods=["GET"])
def list_deductions():
    with _get_session() as db:
        rows = db.query(models.DesignationDeduction).order_by(models.DesignationDeduction.designation).all()
        return jsonify([
            {"id": r.id, "designation": r.designation, "deduction_hours": r.deduction_hours}
            for r in rows
        ])


@entities_bp.route("/designation-deductions", methods=["POST"])
def create_deduction():
    payload = request.get_json(force=True) or {}
    designation = (payload.get("designation") or "").strip()
    deduction_hours = payload.get("deduction_hours")

    if not designation:
        return jsonify({"detail": "Designation is required"}), 400
    if deduction_hours is None or not isinstance(deduction_hours, (int, float)):
        return jsonify({"detail": "Deduction hours must be a number"}), 400

    with _get_session() as db:
        existing = db.query(models.DesignationDeduction).filter(
            models.DesignationDeduction.designation == designation.lower()
        ).first()
        if existing:
            return jsonify({"detail": f"Designation '{designation}' already exists"}), 400

        row = models.DesignationDeduction(
            designation=designation.lower(),
            deduction_hours=int(deduction_hours),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify({"id": row.id, "designation": row.designation, "deduction_hours": row.deduction_hours}), 201


@entities_bp.route("/designation-deductions/<int:deduction_id>", methods=["PUT"])
def update_deduction(deduction_id: int):
    payload = request.get_json(force=True) or {}
    with _get_session() as db:
        row = db.query(models.DesignationDeduction).filter(models.DesignationDeduction.id == deduction_id).first()
        if not row:
            return jsonify({"detail": "Not found"}), 404

        if "designation" in payload:
            new_desig = (payload["designation"] or "").strip().lower()
            if new_desig and new_desig != row.designation:
                dup = db.query(models.DesignationDeduction).filter(
                    models.DesignationDeduction.designation == new_desig,
                    models.DesignationDeduction.id != deduction_id,
                ).first()
                if dup:
                    return jsonify({"detail": f"Designation '{new_desig}' already exists"}), 400
                row.designation = new_desig

        if "deduction_hours" in payload:
            row.deduction_hours = int(payload["deduction_hours"])

        db.commit()
        db.refresh(row)
        return jsonify({"id": row.id, "designation": row.designation, "deduction_hours": row.deduction_hours})


@entities_bp.route("/designation-deductions/<int:deduction_id>", methods=["DELETE"])
def delete_deduction(deduction_id: int):
    with _get_session() as db:
        row = db.query(models.DesignationDeduction).filter(models.DesignationDeduction.id == deduction_id).first()
        if not row:
            return jsonify({"detail": "Not found"}), 404
        db.delete(row)
        db.commit()
        return "", 204


# ---------------------------------------------------------------------------
# Time Block (Time Slots) routes
# ---------------------------------------------------------------------------

def _format_time_label(start_time_str: str, end_time_str: str) -> str:
    """Build a human-readable label like '7:30–9:00' from 24-hour HH:MM strings."""
    def _fmt(t):
        t = (t or "").strip()
        # Handle datetime.time objects
        if hasattr(t, 'strftime'):
            t = t.strftime("%H:%M")
        # Strip leading zero and trailing :00 seconds
        t = re.sub(r":\d{2}$", "", t) if t.count(":") > 1 else t
        parts = t.split(":")
        if len(parts) != 2:
            return t
        h, m = int(parts[0]), int(parts[1])
        return f"{h}:{m:02d}"
    return f"{_fmt(start_time_str)}–{_fmt(end_time_str)}"


def _serialize_time_block(tb) -> dict:
    """Serialize a TimeBlock ORM row to a JSON-safe dict."""
    start_str = tb.start_time.strftime("%H:%M") if hasattr(tb.start_time, "strftime") else str(tb.start_time)
    end_str = tb.end_time.strftime("%H:%M") if hasattr(tb.end_time, "strftime") else str(tb.end_time)
    # Strip seconds if present (e.g. "07:30:00" -> "07:30")
    start_str = re.sub(r":\d{2}$", "", start_str) if start_str.count(":") > 1 else start_str
    end_str = re.sub(r":\d{2}$", "", end_str) if end_str.count(":") > 1 else end_str
    return {
        "block_id": tb.block_id,
        "day_id": tb.day_id,
        "label": tb.label or _format_time_label(start_str, end_str),
        "start_time": start_str,
        "end_time": end_str,
        "start_min": tb.start_min,
        "end_min": tb.end_min,
        "is_lab": bool(tb.is_lab),
    }


@entities_bp.route("/time-blocks", methods=["GET"])
def list_time_blocks():
    """List all time blocks, optionally filtered by day_id."""
    with _get_session() as db:
        q = db.query(models.TimeBlock).order_by(models.TimeBlock.day_id, models.TimeBlock.start_min)
        day_id = request.args.get("day_id", type=int)
        if day_id is not None:
            q = q.filter(models.TimeBlock.day_id == day_id)
        rows = q.all()
        return jsonify([_serialize_time_block(r) for r in rows])


@entities_bp.route("/time-blocks", methods=["POST"])
def create_time_block():
    """Create one or more time blocks.

    Accepts ``day_ids`` (list) to bulk-create the same window across multiple
    days, or a single ``day_id``.
    """
    payload = request.get_json(force=True) or {}

    start_time = (payload.get("start_time") or "").strip()
    end_time = (payload.get("end_time") or "").strip()
    is_lab = bool(payload.get("is_lab", False))

    if not start_time or not end_time:
        return jsonify({"detail": "start_time and end_time are required (HH:MM)"}), 400

    try:
        start_min = _time_str_to_minutes(start_time)
        end_min = _time_str_to_minutes(end_time)
    except Exception:
        return jsonify({"detail": "Invalid time format. Use HH:MM (24-hour)."}), 400

    if end_min <= start_min:
        return jsonify({"detail": "end_time must be after start_time"}), 400

    # Support both single day_id and bulk day_ids
    day_ids = payload.get("day_ids") or []
    if not day_ids:
        single = payload.get("day_id")
        if single is not None:
            day_ids = [int(single)]
    if not day_ids:
        return jsonify({"detail": "day_id or day_ids is required"}), 400

    label = _format_time_label(start_time, end_time)

    created = []
    with _get_session() as db:
        # Validate all day_ids exist
        existing_days = {d.id for d in db.query(models.Day).all()}
        for did in day_ids:
            if int(did) not in existing_days:
                return jsonify({"detail": f"Day ID {did} not found"}), 404

        # Find the max block_id to auto-increment
        max_bid = db.query(models.TimeBlock.block_id).order_by(models.TimeBlock.block_id.desc()).first()
        next_bid = (max_bid[0] + 1) if max_bid else 1

        for did in day_ids:
            # Check for duplicates (same day, same time range, same type)
            dup = db.query(models.TimeBlock).filter(
                models.TimeBlock.day_id == int(did),
                models.TimeBlock.start_min == start_min,
                models.TimeBlock.end_min == end_min,
                models.TimeBlock.is_lab == is_lab,
            ).first()
            if dup:
                # Skip duplicates silently
                continue

            tb = models.TimeBlock(
                block_id=next_bid,
                day_id=int(did),
                label=label,
                start_time=start_time,
                end_time=end_time,
                start_min=start_min,
                end_min=end_min,
                is_lab=is_lab,
            )
            db.add(tb)
            created.append(tb)
            next_bid += 1

        db.commit()
        for tb in created:
            db.refresh(tb)

        return jsonify([_serialize_time_block(tb) for tb in created]), 201


@entities_bp.route("/time-blocks/<int:block_id>", methods=["PUT"])
def update_time_block(block_id: int):
    payload = request.get_json(force=True) or {}
    with _get_session() as db:
        tb = db.query(models.TimeBlock).filter(models.TimeBlock.block_id == block_id).first()
        if not tb:
            return jsonify({"detail": "Time block not found"}), 404

        if "start_time" in payload or "end_time" in payload:
            start_time = (payload.get("start_time") or tb.start_time.strftime("%H:%M") if hasattr(tb.start_time, "strftime") else str(tb.start_time)).strip()
            end_time = (payload.get("end_time") or tb.end_time.strftime("%H:%M") if hasattr(tb.end_time, "strftime") else str(tb.end_time)).strip()
            # Strip seconds
            start_time = re.sub(r":\d{2}$", "", start_time) if start_time.count(":") > 1 else start_time
            end_time = re.sub(r":\d{2}$", "", end_time) if end_time.count(":") > 1 else end_time
            try:
                start_min = _time_str_to_minutes(start_time)
                end_min = _time_str_to_minutes(end_time)
            except Exception:
                return jsonify({"detail": "Invalid time format"}), 400
            if end_min <= start_min:
                return jsonify({"detail": "end_time must be after start_time"}), 400
            tb.start_time = start_time
            tb.end_time = end_time
            tb.start_min = start_min
            tb.end_min = end_min
            tb.label = _format_time_label(start_time, end_time)

        if "is_lab" in payload:
            tb.is_lab = bool(payload["is_lab"])

        if "day_id" in payload:
            tb.day_id = int(payload["day_id"])

        db.commit()
        db.refresh(tb)
        return jsonify(_serialize_time_block(tb))


@entities_bp.route("/time-blocks/<int:block_id>", methods=["DELETE"])
def delete_time_block(block_id: int):
    with _get_session() as db:
        tb = db.query(models.TimeBlock).filter(models.TimeBlock.block_id == block_id).first()
        if not tb:
            return jsonify({"detail": "Time block not found"}), 404
        db.delete(tb)
        db.commit()
        return "", 204


@entities_bp.route("/time-blocks/reset-defaults", methods=["POST"])
def reset_time_blocks_to_defaults():
    """Delete all time blocks and re-seed with the original 14 registrar windows for all existing days."""
    with _get_session() as db:
        # Delete all existing time blocks
        db.query(models.TimeBlock).delete()
        db.commit()

        days = db.query(models.Day).order_by(models.Day.id).all()
        if not days:
            return jsonify({"detail": "No days found in database. Add days first."}), 400

        # The original 14 registrar windows
        registrar_windows = [
            ("07:30", "08:30", False),
            ("09:00", "10:00", False),
            ("10:30", "11:30", False),
            ("07:30", "09:00", True),
            ("09:00", "10:30", True),
            ("10:30", "12:00", True),
            ("13:00", "14:00", False),
            ("14:30", "15:30", False),
            ("16:00", "17:00", False),
            ("13:00", "14:30", True),
            ("14:30", "16:00", True),
            ("16:00", "17:30", True),
            ("17:30", "19:00", False),
            ("08:00", "11:00", False),  # NSTP
        ]

        next_bid = 1
        created = []
        for day in days:
            for start, end, is_lab in registrar_windows:
                s_min = _time_str_to_minutes(start)
                e_min = _time_str_to_minutes(end)
                tb = models.TimeBlock(
                    block_id=next_bid,
                    day_id=day.id,
                    label=_format_time_label(start, end),
                    start_time=start,
                    end_time=end,
                    start_min=s_min,
                    end_min=e_min,
                    is_lab=is_lab,
                )
                db.add(tb)
                created.append(tb)
                next_bid += 1

        db.commit()
        return jsonify({"message": f"Reset {len(created)} time blocks across {len(days)} days", "count": len(created)}), 200
