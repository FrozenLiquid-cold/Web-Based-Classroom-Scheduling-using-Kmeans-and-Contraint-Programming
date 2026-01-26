"""SQLAlchemy models for JRMSU Scheduler"""
from sqlalchemy import Column, Integer, String, ForeignKey, Text, CheckConstraint, UniqueConstraint, Boolean, Time, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

# Import Base from db to avoid circular imports
# This import must be at the top of the file
from .db import Base

# This prevents table redefinition if models are imported multiple times
metadata = Base.metadata


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # 'admin', 'registrar', 'instructor'
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=True)
    
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'registrar', 'instructor')", name="check_role"),
    )
    
    instructor = relationship("Instructor", back_populates="user")


class College(Base):
    __tablename__ = "colleges"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    
    courses = relationship("Course", back_populates="college", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=False)
    
    college = relationship("College", back_populates="courses")
    schedules = relationship("Schedule", back_populates="course")


class Instructor(Base):
    __tablename__ = "instructors"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=False)
    college_id = Column(Integer, ForeignKey("colleges.id"), nullable=True)
    username = Column(String(100), unique=True, nullable=True)
    assignable_courses = Column(Text, nullable=True)  # Comma-separated list of course codes
    employment_type = Column(String(20), nullable=True)
    designation = Column(String(100), nullable=True)
    # Teaching preferences
    preferred_start_time = Column(String(10), nullable=True)  # e.g., "08:00"
    preferred_end_time = Column(String(10), nullable=True)  # e.g., "17:00"
    max_units = Column(Integer, nullable=True)  # Maximum units per semester
    
    college = relationship("College")
    user = relationship("User", back_populates="instructor", uselist=False)
    schedules = relationship("Schedule", back_populates="instructor")


class Day(Base):
    __tablename__ = "days"
    
    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(10), unique=True, nullable=False)  # 'M', 'T', 'W', 'TH', 'F'
    
    schedules = relationship("Schedule", back_populates="day")


class Subject(Base):
    __tablename__ = "subjects"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String(10), nullable=False)  # 'LEC' or 'LAB'
    unit = Column(Integer, nullable=False, default=0)
    is_major = Column(Boolean, nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    # Note: block_id is no longer a subject property - it's selected during CP scheduling from time_blocks table
    recommended_slots = Column(Integer, nullable=True, default=1)  # How many consecutive time slots needed
    cluster = Column(Integer, nullable=True, default=-1)  # For clustering subjects
    min_slots = Column(Integer, nullable=True)  # Minimum slots required
    max_slots = Column(Integer, nullable=True)  # Maximum slots allowed
    year_level = Column(Integer, nullable=True)  # Year level (1-4) for clustering
    semester = Column(Integer, nullable=True)  # Semester (1-2) for clustering
    
    __table_args__ = (
        CheckConstraint("type IN ('LEC', 'LAB')", name="check_subject_type"),
    )
    
    course = relationship("Course")
    schedules = relationship("Schedule", back_populates="subject")


class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(10), nullable=False)  # 'LEC' or 'LAB'
    capacity = Column(Integer, nullable=True)  # Room capacity
    cluster = Column(Integer, nullable=True, default=-1)  # For room clustering
    description = Column(Text, nullable=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    
    __table_args__ = (
        CheckConstraint("type IN ('LEC', 'LAB')", name="check_room_type"),
    )
    
    building = relationship("Building", back_populates="rooms")
    schedules = relationship("Schedule", back_populates="room")


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)

    rooms = relationship("Room", back_populates="building")
    # For distances logic
    distances_from = relationship("BuildingDistance", foreign_keys="[BuildingDistance.from_building_id]", back_populates="from_building")
    distances_to = relationship("BuildingDistance", foreign_keys="[BuildingDistance.to_building_id]", back_populates="to_building")


class BuildingDistance(Base):
    __tablename__ = "building_distances"

    id = Column(Integer, primary_key=True, index=True)
    from_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    to_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    travel_time_minutes = Column(Integer, nullable=False, default=0)

    from_building = relationship("Building", foreign_keys=[from_building_id], back_populates="distances_from")
    to_building = relationship("Building", foreign_keys=[to_building_id], back_populates="distances_to")

    __table_args__ = (
        # Ensure unique pairs
        UniqueConstraint('from_building_id', 'to_building_id', name='uq_building_distance_pair'),
    )


class TimeBlock(Base):
    __tablename__ = "time_blocks"
    
    block_id = Column(Integer, primary_key=True, index=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False, index=True)
    label = Column(String(80), nullable=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    start_min = Column(Integer, nullable=False)
    end_min = Column(Integer, nullable=False)
    is_lab = Column(Boolean, nullable=False, default=False)
    
    day = relationship("Day")

    __table_args__ = (
        UniqueConstraint("block_id", name="uq_time_block_id"),
    )


class Timeslot(Base):
    __tablename__ = "timeslots"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String(50), nullable=True)
    day = Column(Integer, nullable=False)  # 1-5 matching Day IDs
    start_min = Column(Integer, nullable=False)
    end_min = Column(Integer, nullable=False)

    candidates = relationship("Candidate", back_populates="timeslot")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    timeslot_id = Column(Integer, ForeignKey("timeslots.id"), nullable=False)
    semester = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    course = relationship("Course")
    room = relationship("Room")
    timeslot = relationship("Timeslot", back_populates="candidates")


class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    instructor_id = Column(Integer, ForeignKey("instructors.id"), nullable=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=True)
    time = Column(String(50), nullable=True)  # e.g., '7:30–9:00'
    year = Column(Integer, nullable=False)  # 1, 2, 3, 4
    semester = Column(Integer, nullable=False)  # 1, 2
    block = Column(String(50), nullable=True)
    
    subject = relationship("Subject", back_populates="schedules")
    instructor = relationship("Instructor", back_populates="schedules")
    room = relationship("Room", back_populates="schedules")
    course = relationship("Course", back_populates="schedules")
    day = relationship("Day", back_populates="schedules")
    
    __table_args__ = (
        # Prevent double-booking: same room, day, time, year, semester
        UniqueConstraint("room_id", "day_id", "time", "year", "semester", name="uq_room_time"),
        # Prevent instructor conflicts: same instructor, day, time, year, semester
        UniqueConstraint("instructor_id", "day_id", "time", "year", "semester", name="uq_instructor_time"),
    )


class SwapRequest(Base):
    """
    Stores instructor-to-instructor schedule swap requests.
    
    When swapping, only the time/day/room are exchanged between schedules.
    Each instructor keeps teaching their own subject.
    """
    __tablename__ = "swap_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # The schedule the requester wants to swap away
    requester_schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    # The schedule the requester wants to get (from target instructor)
    target_schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    
    # The instructors involved
    requester_id = Column(Integer, ForeignKey("instructors.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("instructors.id"), nullable=False)
    
    # Request details
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending, accepted, rejected
    rejection_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    responded_at = Column(DateTime, nullable=True)
    
    # Relationships
    requester_schedule = relationship("Schedule", foreign_keys=[requester_schedule_id])
    target_schedule = relationship("Schedule", foreign_keys=[target_schedule_id])
    requester = relationship("Instructor", foreign_keys=[requester_id])
    target = relationship("Instructor", foreign_keys=[target_id])
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'rejected')", name="check_swap_status"),
    )
