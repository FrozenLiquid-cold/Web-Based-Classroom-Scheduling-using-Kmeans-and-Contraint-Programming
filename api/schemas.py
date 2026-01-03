"""Pydantic schemas for request/response validation"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import time


# User schemas
class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    instructor_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    """Schema for authenticated user profile updates.

    Currently used by instructors to update their own username,
    password, and eligible subject codes (assignable_courses).
    """

    username: Optional[str] = None
    password: Optional[str] = None
    assignable_courses: Optional[str] = None


class SessionResponse(BaseModel):
    role: str
    username: str
    instructor_id: Optional[int] = None


# College schemas
class CollegeCreate(BaseModel):
    code: str
    description: str


class CollegeUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None


class CollegeResponse(BaseModel):
    id: int
    code: str
    description: str

    class Config:
        from_attributes = True


# Course schemas
class CourseCreate(BaseModel):
    code: str
    description: str
    college_id: int


class CourseUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    college_id: Optional[int] = None


class CourseResponse(BaseModel):
    id: int
    code: str
    description: str
    college_id: int

    class Config:
        from_attributes = True


# Instructor schemas
class InstructorCreate(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    college_id: Optional[int] = None
    username: Optional[str] = None
    assignable_courses: Optional[str] = None
    employment_type: Optional[str] = None
    designation: Optional[str] = None
    password: Optional[str] = None


class InstructorUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    college_id: Optional[int] = None
    username: Optional[str] = None
    assignable_courses: Optional[str] = None
    employment_type: Optional[str] = None
    designation: Optional[str] = None


class InstructorResponse(BaseModel):
    id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    college_id: Optional[int] = None
    username: Optional[str] = None
    assignable_courses: Optional[str] = None
    employment_type: Optional[str] = None
    designation: Optional[str] = None

    class Config:
        from_attributes = True


# Day schemas
class DayCreate(BaseModel):
    label: str


class DayResponse(BaseModel):
    id: int
    label: str

    class Config:
        from_attributes = True


# Subject schemas
class SubjectCreate(BaseModel):
    code: str
    description: str
    type: str  # 'LEC' or 'LAB'
    unit: int
    year_level: int
    semester: int
    is_major: Optional[bool] = None
    course_id: Optional[int] = None
    # Note: block_id is no longer a subject property - it's selected during CP scheduling from time_blocks table


class SubjectUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    unit: Optional[int] = None
    year_level: Optional[int] = None
    semester: Optional[int] = None
    is_major: Optional[bool] = None
    course_id: Optional[int] = None
    # Note: block_id is no longer a subject property


class SubjectResponse(BaseModel):
    id: int
    code: str
    description: str
    type: str
    unit: int
    year_level: Optional[int] = None
    semester: Optional[int] = None
    is_major: Optional[bool] = None
    course_id: Optional[int] = None
    # Note: block_id is no longer a subject property - it's selected during CP scheduling

    class Config:
        from_attributes = True


# Room schemas
class RoomCreate(BaseModel):
    name: str
    type: str  # 'LEC' or 'LAB'


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None


class RoomResponse(BaseModel):
    id: int
    name: str
    type: str

    class Config:
        from_attributes = True


# Schedule schemas
class ScheduleItemCreate(BaseModel):
    subject_id: int
    instructor_id: Optional[int] = None
    room_id: Optional[int] = None
    day_id: Optional[int] = None
    time: Optional[str] = None  # e.g., '7:30–9:00'
    block: Optional[str] = None


class ScheduleItemResponse(BaseModel):
    id: int
    subject_id: int
    instructor_id: Optional[int] = None
    room_id: Optional[int] = None
    course_id: int
    day_id: Optional[int] = None
    time: Optional[str] = None
    year: int
    semester: int
    block: Optional[str] = None

    class Config:
        from_attributes = True


class ScheduleGenerateRequest(BaseModel):
    course_id: int
    year: Optional[int] = None  # Legacy single-year support
    years: Optional[List[int]] = None  # New multi-year support
    semester: int
    subject_ids: Optional[List[int]] = None  # If None, use all subjects
    use_kmeans: Optional[bool] = True  # Run K-Means clustering before scheduling
    k_clusters: Optional[int] = 3  # Number of clusters for K-Means
    weight_slots: Optional[float] = 2.0  # Weight multiplier for recommended_slots
    force_refit: Optional[bool] = False  # Force re-run clustering even if cache exists
    block_capacities: Optional[List["BlockCapacityOverride"]] = None  # Optional per-block capacity overrides
    blocks_count: Optional[int] = None  # Optional number of student blocks (A/B/...) per course/year


class BlockCapacityOverride(BaseModel):
    course_id: int
    year: int
    block_id: str
    capacity: int


ScheduleGenerateRequest.model_rebuild()

 
class ScheduleSaveRequest(BaseModel):
    course_id: int
    year: int
    semester: int
    items: List[ScheduleItemCreate]


