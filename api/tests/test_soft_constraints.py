
import pytest
from dataclasses import dataclass
from typing import List, Dict, Any, Set
from collections import defaultdict
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the greedy function specifically
from scheduler.cp_scheduler import greedy_initial_schedule

# Mock Models
@dataclass
class Subject:
    id: int
    course_id: int
    code: str
    type: str = 'LEC'
    unit: int = 3
    enrollment: int = 30
    recommended_slots: int = 2
    min_slots: int = 2
    year_level: int = 1

@dataclass
class Room:
    id: int
    name: str
    type: str = 'LEC'
    capacity: int = 40

@dataclass
class Day:
    id: int
    label: str

@dataclass
class Instructor:
    id: int
    name: str

# Mock is_consecutive_blocks since we use custom time slots
import scheduler.cp_scheduler
scheduler.cp_scheduler.is_consecutive_blocks = lambda x: True

def test_greedy_soft_room_constraints():
    # Setup Data
    subject1 = Subject(id=101, course_id=1, code="SUBJ101")
    cluster_subjects = [subject1]
    
    room_pref = Room(id=1, name="PreferredRoom")
    room_other = Room(id=2, name="OtherRoom")
    room_small = Room(id=3, name="SmallRoom", capacity=10) # Too small
    rooms = [room_pref, room_other, room_small]
    
    days = [Day(id=1, label="M")]
    
    # Setup Slots: M 8:00-9:00 (2 slots assuming 30min blocks)
    slots_by_day = {
        "M": [
            {"index": 1, "start_min": 480, "end_min": 510, "label": "8:00"},
            {"index": 2, "start_min": 510, "end_min": 540, "label": "8:30"},
            {"index": 3, "start_min": 540, "end_min": 570, "label": "9:00"}, # Extra slot
        ]
    }
    
    # Case 1: Preferred Room Available -> Should choose PreferredRoom
    course_to_instructors = {101: [501]} # instr_id
    course_to_all_rooms = {101: [1, 2, 3]}
    course_to_preferred_rooms = {101: [1]}
    
    booked_rooms = set()
    booked_instrs = set()
    
    hints = greedy_initial_schedule(
        cluster_subjects,
        course_to_instructors,
        course_to_all_rooms,
        course_to_preferred_rooms,
        slots_by_day,
        booked_rooms,
        booked_instrs,
        rooms,
        days
    )
    
    # Verify: Should match (subject_id, room_id, start, instructor_id, duration)
    # Expected: (101, 1, 1, 501, 2)
    assert len(hints) == 1
    key = list(hints.keys())[0]
    assert key[0] == 101 # Subject
    assert key[1] == 1   # Room 1 (Preferred)
    assert key[3] == 501 # Instructor
    
    print("\n[PASS] Case 1: Preferred room chosen when available")
    
    # Case 2: Preferred Room Booked -> Should fallback to OtherRoom
    # Book PreferredRoom for the time slot
    booked_rooms = {("PreferredRoom", 1, 1), ("PreferredRoom", 1, 2)}
    booked_instrs = set()
    
    hints = greedy_initial_schedule(
        cluster_subjects,
        course_to_instructors,
        course_to_all_rooms,
        course_to_preferred_rooms, # Still prefer 1
        slots_by_day,
        booked_rooms,
        booked_instrs,
        rooms,
        days
    )
    
    assert len(hints) == 1
    key = list(hints.keys())[0]
    assert key[0] == 101
    assert key[1] == 2   # Room 2 (Other - fallback)
    # Should NOT be 1 (Booked) or 3 (Too Small)
    
    print("[PASS] Case 2: Fallback to valid non-preferred room when preferred is booked")

    # Case 3: All Valid Rooms Booked -> Should schedule nothing
    booked_rooms = {
        ("PreferredRoom", 1, 1), ("PreferredRoom", 1, 2),
        ("OtherRoom", 1, 1), ("OtherRoom", 1, 2)
    }
    
    hints = greedy_initial_schedule(
        cluster_subjects,
        course_to_instructors,
        course_to_all_rooms,
        course_to_preferred_rooms,
        slots_by_day,
        booked_rooms,
        booked_instrs,
        rooms,
        days
    )
    
    assert len(hints) == 0
    print("[PASS] Case 3: No scheduling when all valid rooms booked")

if __name__ == "__main__":
    test_greedy_soft_room_constraints()
