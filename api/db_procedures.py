"""
Database stored procedure helpers for optimized queries.

This module provides Python wrappers for PostgreSQL stored procedures
to ensure optimal query performance and avoid N+1 query problems.
"""
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from api import models


def get_instructor_availability(
    db: Session,
    instructor_id: int,
    semester: int,
    year: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get available time slots for an instructor using stored procedure.
    
    Args:
        db: Database session
        instructor_id: Instructor ID
        semester: Semester (1-2)
        year: Optional year level filter
    
    Returns:
        List of available time slots with day_id, day_label, time_label, start_min, end_min
    """
    result = db.execute(
        text("SELECT * FROM get_instructor_availability(:instr_id, :semester, :year)"),
        {"instr_id": instructor_id, "semester": semester, "year": year}
    )
    return [
        {
            "day_id": row.day_id,
            "day_label": row.day_label,
            "time_label": row.time_label,
            "start_min": row.start_min,
            "end_min": row.end_min
        }
        for row in result
    ]


def get_available_rooms(
    db: Session,
    room_type: str,
    min_capacity: Optional[int] = None,
    semester: Optional[int] = None,
    year: Optional[int] = None,
    day_id: Optional[int] = None,
    time_label: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get available rooms filtered by type and capacity using stored procedure.
    
    Args:
        db: Database session
        room_type: Room type ('LEC' or 'LAB')
        min_capacity: Optional minimum capacity filter
        semester: Optional semester for availability check
        year: Optional year for availability check
        day_id: Optional day ID for availability check
        time_label: Optional time label for availability check
    
    Returns:
        List of available rooms with room_id, room_name, room_type, capacity, cluster
    """
    result = db.execute(
        text("""
            SELECT * FROM get_available_rooms(
                :p_type, :p_min_capacity, :p_semester, :p_year, :p_day_id, :p_time_label
            )
        """),
        {
            "p_type": room_type,
            "p_min_capacity": min_capacity,
            "p_semester": semester,
            "p_year": year,
            "p_day_id": day_id,
            "p_time_label": time_label
        }
    )
    return [
        {
            "room_id": row.room_id,
            "room_name": row.room_name,
            "room_type": row.room_type,
            "capacity": row.capacity,
            "cluster": row.cluster
        }
        for row in result
    ]


def get_existing_bookings(
    db: Session,
    semester: int,
    years: Optional[List[int]] = None,
    exclude_course_id: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Get existing room and instructor bookings using stored procedure.
    
    Args:
        db: Database session
        semester: Semester (1-2)
        years: Optional list of years to filter
        exclude_course_id: Optional course ID to exclude from bookings
    
    Returns:
        Tuple of (room_bookings, instructor_bookings) where each is a list of dicts
        with booking_type, resource_id, resource_name, day_id, time_label
    """
    years_array = years if years else None
    result = db.execute(
        text("SELECT * FROM get_existing_bookings(:p_semester, :p_years, :p_exclude_course_id)"),
        {
            "p_semester": semester,
            "p_years": years_array,
            "p_exclude_course_id": exclude_course_id
        }
    )
    
    room_bookings = []
    instructor_bookings = []
    
    for row in result:
        booking = {
            "resource_id": row.resource_id,
            "resource_name": row.resource_name,
            "day_id": row.day_id,
            "time_label": row.time_label
        }
        if row.booking_type == "room":
            room_bookings.append(booking)
        else:
            instructor_bookings.append(booking)
    
    return room_bookings, instructor_bookings


def get_subjects_for_scheduling(
    db: Session,
    course_id: Optional[int] = None,
    college_id: Optional[int] = None,
    cluster_id: Optional[int] = None,
    subject_ids: Optional[List[int]] = None,
    year_level: Optional[int] = None,
    semester: Optional[int] = None
) -> List[models.Subject]:
    """
    Get subjects for scheduling using stored procedure.
    
    Args:
        db: Database session
        course_id: Optional course ID filter
        college_id: Optional college ID filter
        cluster_id: Optional cluster ID filter
        subject_ids: Optional list of subject IDs to filter
        year_level: Optional year level filter
        semester: Optional semester filter
    
    Returns:
        List of Subject models
    """
    result = db.execute(
        text("""
            SELECT * FROM get_subjects_for_scheduling(
                :p_course_id, :p_college_id, :p_cluster_id, :p_subject_ids,
                :p_year_level, :p_semester
            )
        """),
        {
            "p_course_id": course_id,
            "p_college_id": college_id,
            "p_cluster_id": cluster_id,
            "p_subject_ids": subject_ids,
            "p_year_level": year_level,
            "p_semester": semester
        }
    )

    subjects: List[models.Subject] = []
    for row in result:
        subjects.append(
            models.Subject(
                id=row.subject_id,
                course_id=row.course_id,
                code=row.code,
                description=row.description,
                type=row.type,
                unit=row.unit,
                recommended_slots=row.recommended_slots,
                cluster=row.cluster,
                min_slots=row.min_slots,
                max_slots=row.max_slots,
                year_level=row.year_level,
                semester=row.semester,
            )
        )

    return subjects


def get_instructor_eligibility(
    db: Session,
    subject_id: int
) -> List[models.Instructor]:
    """
    Get instructors eligible to teach a subject using stored procedure.
    
    Args:
        db: Database session
        subject_id: Subject ID
    
    Returns:
        List of eligible Instructor models
    """
    result = db.execute(
        text("SELECT * FROM get_instructor_eligibility(:p_subject_id)"),
        {"p_subject_id": subject_id}
    )
    
    instructors = []
    for row in result:
        instructor = models.Instructor(
            id=row.instructor_id,
            first_name=row.first_name,
            last_name=row.last_name,
            college_id=row.college_id,
            assignable_courses=row.assignable_courses
        )
        instructors.append(instructor)
    
    return instructors


def get_room_eligibility(
    db: Session,
    subject_id: int,
    min_capacity: Optional[int] = None
) -> List[models.Room]:
    """
    Get rooms eligible for a subject using stored procedure.
    
    Args:
        db: Database session
        subject_id: Subject ID
        min_capacity: Optional minimum capacity filter
    
    Returns:
        List of eligible Room models
    """
    result = db.execute(
        text("SELECT * FROM get_room_eligibility(:p_subject_id, :p_min_capacity)"),
        {"p_subject_id": subject_id, "p_min_capacity": min_capacity}
    )
    
    rooms = []
    for row in result:
        room = models.Room(
            id=row.room_id,
            name=row.room_name,
            type=row.room_type,
            capacity=row.capacity,
            cluster=row.cluster
        )
        rooms.append(room)
    
    return rooms


def get_schedules_for_course(
    db: Session,
    course_id: int,
    semester: int,
    year: Optional[int] = None,
    instructor_id: Optional[int] = None
) -> List[models.Schedule]:
    """
    Get schedules for a course using stored procedure.
    
    Args:
        db: Database session
        course_id: Course ID
        semester: Semester (1-2)
        year: Optional year level filter
        instructor_id: Optional instructor ID filter
    
    Returns:
        List of Schedule models
    """
    result = db.execute(
        text("""
            SELECT * FROM get_schedules_for_course(
                :p_course_id, :p_semester, :p_year, :p_instructor_id
            )
        """),
        {
            "p_course_id": course_id,
            "p_semester": semester,
            "p_year": year,
            "p_instructor_id": instructor_id
        }
    )
    
    schedules = []
    for row in result:
        # Include block column if present so block labels (A, B, etc.) are preserved
        block_value = getattr(row, "block", None)

        schedule = models.Schedule(
            id=row.schedule_id,
            subject_id=row.subject_id,
            instructor_id=row.instructor_id,
            room_id=row.room_id,
            day_id=row.day_id,
            time=row.time_label,
            course_id=row.course_id,
            year=row.year,
            semester=row.semester,
            block=block_value,
        )
        schedules.append(schedule)
    
    return schedules


def get_instructor_schedules(
    db: Session,
    instructor_id: int,
    semester: Optional[int] = None
) -> List[models.Schedule]:
    """
    Get all schedules for an instructor using stored procedure.
    
    This is optimized to fetch all instructor schedules in a single query,
    eliminating the need for N+1 queries when loading instructor schedule pages.
    
    Args:
        db: Database session
        instructor_id: Instructor ID
        semester: Optional semester filter (1 or 2)
    
    Returns:
        List of Schedule models containing all schedules for the instructor
    """
    try:
        # Try using the stored procedure first
        result = db.execute(
            text("SELECT * FROM get_instructor_schedules(:p_instructor_id, :p_semester)"),
            {"p_instructor_id": instructor_id, "p_semester": semester}
        )
        
        schedules = []
        for row in result:
            schedule = models.Schedule(
                id=row.id,
                subject_id=row.subject_id,
                instructor_id=row.instructor_id,
                room_id=row.room_id,
                day_id=row.day_id,
                time=row.time,
                course_id=row.course_id,
                year=row.year,
                semester=row.semester,
                block=row.block,
            )
            schedules.append(schedule)
        
        return schedules
    except Exception:
        # Fall back to direct query if stored procedure doesn't exist
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
        
        return query.all()


def get_courses_by_college(
    db: Session,
    college_id: int
) -> List[models.Course]:
    """
    Get all courses for a college using stored procedure.
    
    Args:
        db: Database session
        college_id: College ID
    
    Returns:
        List of Course models
    """
    result = db.execute(
        text("SELECT * FROM get_courses_by_college(:p_college_id)"),
        {"p_college_id": college_id}
    )
    
    courses = []
    for row in result:
        course = models.Course(
            id=row.course_id,
            code=row.code,
            description=row.description,
            college_id=row.college_id
        )
        courses.append(course)
    
    return courses


def get_timeslots_by_day(
    db: Session,
    day_id: int
) -> List[models.Timeslot]:
    """
    Get all time slots for a specific day using stored procedure.
    
    Args:
        db: Database session
        day_id: Day ID
    
    Returns:
        List of Timeslot models
    """
    result = db.execute(
        text("SELECT * FROM get_timeslots_by_day(:p_day_id)"),
        {"p_day_id": day_id}
    )
    
    timeslots = []
    for row in result:
        timeslot = models.Timeslot(
            id=row.timeslot_id,
            label=row.label,
            day=row.day,
            start_min=row.start_min,
            end_min=row.end_min
        )
        timeslots.append(timeslot)
    
    return timeslots


def execute_migration(db: Session, migration_file: str) -> None:
    """
    Execute a SQL migration file.
    
    Args:
        db: Database session
        migration_file: Path to SQL migration file
    """
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    # Split by semicolons and execute each statement
    statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]
    
    for statement in statements:
        if statement:
            try:
                db.execute(text(statement))
            except Exception as e:
                # Skip if already exists (for idempotent migrations)
                if "already exists" not in str(e).lower():
                    raise
    
    db.commit()

