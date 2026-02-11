# api/tests/test_cp_solver_patterns.py
import pytest
import types
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
from collections import defaultdict
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import the CP scheduler module. If missing, skip tests.
cp_scheduler = pytest.importorskip("scheduler.cp_scheduler", reason="scheduler.cp_scheduler module not found")

# -----------------------------------------------------------------------------
# Minimal model-like dataclasses to mimic ORM objects used by the scheduler.
# Add or remove attributes to match your real models as needed.
# -----------------------------------------------------------------------------
@dataclass
class Subject:
    id: int
    course_id: int
    code: str
    type: str  # 'LEC' or 'LAB'
    unit: int
    cluster: int = 0
    enrollment: int = 20  # used for capacity checks
    year_level: int = 1
    semester: int = 1
    min_slots: int = 1
    max_slots: int = 1
    recommended_slots: int = 1
    original_subject_id: int = None
    student_block: int = 1

@dataclass
class Instructor:
    id: int
    college_id: int = None
    assignable_courses: str = ""  # comma-separated subject codes
    name: str = "Instructor"

@dataclass
class Room:
    id: int
    type: str  # match subject.type
    capacity: int = 40
    name: str = "Room"

# -----------------------------------------------------------------------------
# Shared fixtures: a small time-block universe matching the scheduler's expectations.
# The scheduler in the project uses day ids (1..5) mapping to days ['F','M','T','TH','W'].
# We will provide time block indexes and blocks_by_day for options.
# -----------------------------------------------------------------------------
@pytest.fixture
def simple_time_blocks():
    """
    Returns:
      - time_blocks: list/dict expected by your project (if used)
      - blocks_by_day: mapping day_id -> set(block indices) used by generate_subject_start_options
    """
    # We assume block indices 10..11 represent a single-hour meeting in tests.
    blocks_by_day = {
        # day_id : available block indices for a candidate meeting slot
        1: {10, 11},  # F
        2: {10, 11},  # M
        3: {10, 11},  # T
        4: {10, 11},  # TH
        5: {10, 11},  # W
    }
    # Some schedulers expect a list of block objects. Keep it minimal:
    time_blocks = [{"id": b} for day in blocks_by_day for b in blocks_by_day[day]]
    return {"time_blocks": time_blocks, "blocks_by_day": blocks_by_day}

# -----------------------------------------------------------------------------
# Utility: robust wrapper to call the project's solver.
# It will try a few common signatures and return the solver result if successful.
# If none match, it will raise pytest.skip with instructions.
# -----------------------------------------------------------------------------
def call_solver(subjects: List[Subject], instructors: List[Instructor], rooms: List[Room], time_info: Dict[str, Any], max_time: float = 15.0):
    """
    Adapter that calls the actual scheduler logic (cp_scheduler._cp_retry_mini_model)
    by constructing the necessary maps and parameters expected by the internal solver.
    """
    # 1. Construct Mock Days
    # Fixture assumes 1=F, 2=M, 3=T, 4=TH, 5=W based on comments (though usually 1=M in project...)
    # Let's trust the fixture comments passed in.
    # Actually, cp_scheduler relies on Day.label to match pattern ("M", "W").
    # We must ensure the day IDs in blocks_by_day match the labels we provide here.
    # Fixture: 1: {10,11} (F). So Day(id=1, label="F")
    day_map = {
        1: "F",
        2: "M",
        3: "T",
        4: "TH",
        5: "W",
        6: "SAT",
        7: "SUN"
    }
    mock_days = []
    for did, label in day_map.items():
        # Create a mock Day object. Using types.SimpleNamespace or just a class
        d = types.SimpleNamespace(id=did, label=label)
        mock_days.append(d)

    # 2. Construct slots_by_day from time_info['blocks_by_day']
    # The solver expects slots to be dicts with 'index', 'start_min', 'end_min'.
    # We'll assume index 10 = 10:00 (600 min).
    blocks_by_day = time_info.get("blocks_by_day", {})
    slots_by_day = {}
    
    for did, indices in blocks_by_day.items():
        label = day_map.get(did)
        if not label: continue
        
        day_slots = []
        # Sort indices to ensure order
        for idx in sorted(indices):
            # Synthetic time: index * 60
            day_slots.append({
                "index": idx,
                "start_min": idx * 60,
                "end_min": (idx + 1) * 60,
                "label": f"{idx}:00 - {idx+1}:00",
                "start": f"{idx}:00",
                "end": f"{idx+1}:00"
            })
        slots_by_day[label] = day_slots

    # 3. Construct Eligibility Maps
    # cp_scheduler expects Dict[str, List[int]] where key is Subject ID
    # Note: cp_scheduler uses str(subject_id) or int? 
    # In _cp_retry_mini_model: eligible_instrs = course_to_instructors.get(subject.id, [])
    # So keys should be subject.id (int).
    
    course_to_instructors = {}
    course_to_rooms = {}
    
    for s in subjects:
        # Instructors
        eligible_i = []
        for i in instructors:
            # Check assignable_courses (comma sep)
            assignable = [c.strip().upper() for c in i.assignable_courses.split(",")]
            if s.code.upper() in assignable:
                eligible_i.append(i.id)
        course_to_instructors[s.id] = eligible_i
        
        # Rooms (match type)
        eligible_r = []
        for r in rooms:
            if r.type == s.type:
                eligible_r.append(r.id)
        course_to_rooms[s.id] = eligible_r

    # 4. Call _cp_retry_mini_model
    # It requires many args, we pass defaults or empty collections for most.
    try:
        results, _ = cp_scheduler._cp_retry_mini_model(
            db=None, # Mock DB
            unscheduled_subjects=subjects,
            course_to_instructors=course_to_instructors,
            course_to_rooms=course_to_rooms,
            slots_by_day=slots_by_day,
            booked_room_slots_global=set(),
            booked_instr_slots_global=set(),
            rooms=rooms,
            days=mock_days,
            room_id_to_name={r.id: r.name for r in rooms},
            course_id=1,
            default_year=1,
            semester=1,
            focus_subject_ids_set=None,
            lec_instructor_by_key={},
            student_time_ranges=defaultdict(list),
            relaxed=True
        )
        
        # 5. Flatten results to list
        # results is Dict[subject_id, ScheduleItem | List[ScheduleItem]]
        flat_schedule = []
        for val in results.values():
            if isinstance(val, list):
                flat_schedule.extend(val)
            else:
                flat_schedule.append(val)
                
        return flat_schedule

    except Exception as e:
        # If call fails, raise it to see traceback
        raise e

# -----------------------------------------------------------------------------
# Helper: interpret solver output in a few common shapes (list of scheduled dicts, or object)
# We'll return a normalized list of scheduled items with keys:
#   { 'subject_id': int, 'days': List[str] or List[int], 'room': room_id or name, 'instructor': instructor_id or name }
# -----------------------------------------------------------------------------
def normalize_schedule_output(raw):
    # If raw is already a list of dict-like scheduled items, return directly
    if isinstance(raw, list):
        return raw
    # If raw has attribute 'items' or 'schedule', try to extract
    if hasattr(raw, "items"):
        return list(raw.items)
    if hasattr(raw, "schedule"):
        return list(raw.schedule)
    # Last resort: return raw as single-item list
    return [raw]

# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------
@pytest.mark.integration
def test_cp_solver_schedules_mw_pattern(simple_time_blocks):
    """
    Create 1 LEC subject that requires MW pattern and verify solver schedules it
    with 2 meetings (M and W).
    """
    # Arrange
    subj = Subject(id=1, course_id=1, code="MW01", type="LEC", unit=3)
    # Keep single instructor and rooms that match type
    instr = Instructor(id=10, college_id=None, assignable_courses="MW01")
    room_mw = Room(id=100, type="LEC", capacity=50, name="Phys Lab")

    subjects = [subj]
    instructors = [instr]
    rooms = [room_mw]
    
    # Restrict slots to M(2) and W(5) only to force MW pattern
    # Otherwise solver might pick F fallback since cost is equal
    blocks = simple_time_blocks['blocks_by_day'].copy()
    blocks = {d: blocks[d] for d in [2, 5] if d in blocks} 
    time_info = {'blocks_by_day': blocks, 'time_blocks': simple_time_blocks['time_blocks']}

    # Act
    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    # Assert: at least one scheduled item for our subject, and that it uses 2 days
    assert schedule, "Solver returned no schedule"
    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, f"No schedule item for subject {subj.id}"
    
    unique_days = set()
    for item in s_items:
        val = item.get("day_id")
        if val: unique_days.add(val)
        
    assert len(unique_days) == 2, f"MW subject expected 2 meetings, found {len(unique_days)} (days: {unique_days})"


@pytest.mark.integration
def test_cp_solver_schedules_tth_pattern(simple_time_blocks):
    """
    Verify TTh LEC is scheduled with 2 meetings.
    """
    subj = Subject(id=2, course_id=2, code="TTH01", type="LEC", unit=3)
    instr = Instructor(id=11, assignable_courses="TTH01")
    room = Room(id=101, type="LEC", capacity=40, name="GS ER 1")

    subjects = [subj]
    instructors = [instr]
    rooms = [room]
    
    # Restrict to T(3), TH(4)
    blocks = simple_time_blocks['blocks_by_day'].copy()
    blocks = {d: blocks[d] for d in [3, 4] if d in blocks}
    time_info = {'blocks_by_day': blocks, 'time_blocks': simple_time_blocks['time_blocks']}

    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, f"No schedule item for subject {subj.id}"
    
    unique_days = set()
    for item in s_items:
        val = item.get("day_id")
        if val: unique_days.add(val)
        
    assert len(unique_days) == 2, f"TTh subject expected 2 meetings, got {unique_days}"


@pytest.mark.integration
def test_cp_solver_schedules_friday_single(simple_time_blocks):
    """
    Verify F-only LEC is scheduled once.
    """
    subj = Subject(id=3, course_id=3, code="FRI01", type="LEC", unit=3)
    instr = Instructor(id=12, assignable_courses="FRI01")
    room = Room(id=102, type="LEC", capacity=40, name="GS ER 2")

    subjects = [subj]
    instructors = [instr]
    rooms = [room]
    
    # Restrict to F(1)
    blocks = simple_time_blocks['blocks_by_day'].copy()
    blocks = {d: blocks[d] for d in [1] if d in blocks}
    time_info = {'blocks_by_day': blocks, 'time_blocks': simple_time_blocks['time_blocks']}

    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, "No schedule item for FRIDAY subject"
    
    unique_days = set()
    for item in s_items:
        val = item.get("day_id")
        if val: unique_days.add(val)
        
    assert len(unique_days) == 1, f"Friday LEC should be single meeting, got {unique_days}"


@pytest.mark.integration
def test_cp_solver_schedules_lab_single_meeting(simple_time_blocks):
    """
    Verify LAB subject is scheduled once on some day (labs are single meeting).
    """
    subj = Subject(id=4, course_id=4, code="LAB01", type="LAB", unit=1)
    instr = Instructor(id=13, assignable_courses="LAB01")
    room = Room(id=103, type="LAB", capacity=30, name="Comp Lab 1")

    subjects = [subj]
    instructors = [instr]
    rooms = [room]
    time_info = simple_time_blocks

    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, "No schedule item for LAB subject"
    unique_days = set()
    for item in s_items:
        val = item.get("day_id")
        if val: unique_days.add(val)
        
    assert len(unique_days) == 1, f"LAB subject should be single meeting, got {unique_days}"

# -----------------------------------------------------------------------------
# Helpful note: if tests are skipped due to incompatible function signature,
# edit call_solver() above to adapt to your actual API. The tests show the
# shapes of data provided to the solver (lists of Subject/Instructor/Room dataclasses).
# -----------------------------------------------------------------------------
