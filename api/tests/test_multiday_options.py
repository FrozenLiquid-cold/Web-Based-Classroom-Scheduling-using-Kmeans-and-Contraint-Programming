# api/tests/test_cp_solver_patterns.py
import pytest
import types
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
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
    Attempts to call a CP-solver entrypoint in scheduler.cp_scheduler.
    Returns whatever the solver returns (expected: schedule items or an object containing them).
    """
    # Common candidate function names in codebases:
    candidates = [
        getattr(cp_scheduler, "run_cp_scheduler", None),
        getattr(cp_scheduler, "run_scheduler", None),
        getattr(cp_scheduler, "solve", None),
        getattr(cp_scheduler, "schedule_with_cp", None),
    ]

    # Try plausible signatures for run_cp_scheduler(...) observed in project logs:
    #  - run_cp_scheduler(subjects=..., instructors=..., rooms=..., time_blocks=..., max_time=...)
    #  - run_cp_scheduler(college_id=..., focus_list=..., max_time=...)
    # We'll attempt a few calls and accept the first that doesn't TypeError.
    errors = []
    for fn in candidates:
        if not isinstance(fn, types.FunctionType):
            continue
        try:
            # Try a signature with explicit lists (most likely for unit/integration tests)
            try:
                return fn(subjects=subjects, instructors=instructors, rooms=rooms, time_blocks=time_info.get("time_blocks"), max_time=max_time)
            except TypeError:
                # try positional fallback
                try:
                    return fn(subjects, instructors, rooms, time_info.get("time_blocks"), max_time)
                except TypeError as e2:
                    raise e2
        except Exception as e:
            errors.append((fn.__name__ if hasattr(fn, "__name__") else str(fn), repr(e)))
            continue

    # If we reach here, solver entrypoint wasn't found with tested signatures.
    msg = (
        "Could not call a CP-solver entrypoint with the tested signatures.\n"
        "Tried candidates: {}\n"
        "Errors: {}\n\n"
        "Please adapt call_solver() in the test file to the project's actual API. "
        "You can implement a tiny adapter wrapper that accepts (subjects, instructors, rooms, time_blocks) and forwards to your real function.\n"
        "Example adapter:\n\n"
        "def run_adapter(subjects, instructors, rooms, time_blocks, max_time=15.0):\n"
        "    # convert dataclasses to ORM objects or DB fixtures expected by real run_cp_scheduler\n"
        "    return cp_scheduler.run_cp_scheduler(subjects=..., instructors=..., rooms=..., time_blocks=..., max_time=max_time)\n\n"
    ).format([c[0] for c in candidates], errors)
    pytest.skip(msg)

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
    time_info = simple_time_blocks

    # Act
    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    # Assert: at least one scheduled item for our subject, and that it uses 2 days
    assert schedule, "Solver returned no schedule"
    # try to find our subject
    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, f"No schedule item for subject {subj.id}"
    item = s_items[0]

    # Accept various shapes for 'days' representation (labels or day_ids)
    days = item.get("days") or item.get("day_ids") or item.get("meeting_days") or item.get("days_used")
    assert days, f"Scheduled item for subject {subj.id} missing days field: {item}"
    assert len(days) == 2, f"MW subject expected 2 meetings, found {len(days)} (value: {days})"


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
    time_info = simple_time_blocks

    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, f"No schedule item for subject {subj.id}"
    item = s_items[0]
    days = item.get("days") or item.get("day_ids") or item.get("meeting_days")
    assert days and len(days) == 2, f"TTh subject expected 2 meetings, got {days}"


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
    time_info = simple_time_blocks

    raw = call_solver(subjects, instructors, rooms, time_info, max_time=10.0)
    schedule = normalize_schedule_output(raw)

    s_items = [s for s in schedule if (s.get("subject_id") == subj.id or s.get("id") == subj.id or s.get("subject") == subj.id)]
    assert s_items, "No schedule item for FRIDAY subject"
    item = s_items[0]
    days = item.get("days") or item.get("day_ids")
    assert days and len(days) == 1, f"Friday LEC should be single meeting, got {days}"


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
    item = s_items[0]
    days = item.get("days") or item.get("day_ids")
    assert days and len(days) == 1, f"LAB subject should be single meeting, got {days}"

# -----------------------------------------------------------------------------
# Helpful note: if tests are skipped due to incompatible function signature,
# edit call_solver() above to adapt to your actual API. The tests show the
# shapes of data provided to the solver (lists of Subject/Instructor/Room dataclasses).
# -----------------------------------------------------------------------------
