"""Slot availability analysis and recommendation generation for scheduling."""
from typing import List, Dict, Tuple, Optional, Any, Set
from collections import defaultdict
from sqlalchemy.orm import Session
from api import models
from .timeslots import TIME_BLOCKS, time_to_minutes


def get_available_slots(
    rooms: List[models.Room],
    days: List[models.Day],
    booked_room_ranges: Dict[Tuple[Any, int], List[Tuple[int, int]]],
) -> Dict[int, Dict[int, List[Dict]]]:
    """
    Scan all rooms and find available time slots.
    
    Args:
        rooms: List of Room models
        days: List of Day models
        booked_room_ranges: Existing bookings {(room_name, day_id): [(start_min, end_min), ...]}
    
    Returns:
        {room_id: {day_id: [{"start_min": x, "end_min": y, "label": "7:00-8:30"}, ...]}}
    """
    available = defaultdict(lambda: defaultdict(list))
    room_name_to_id = {r.name: r.id for r in rooms}
    
    for room in rooms:
        for day in days:
            room_key = (room.name, day.id)
            booked_ranges = booked_room_ranges.get(room_key, [])
            
            # Check each time block
            for block in TIME_BLOCKS:
                start_min = time_to_minutes(block["start"])
                end_min = time_to_minutes(block["end"])
                
                # Check if this slot overlaps with any booked range
                is_free = True
                for entry in booked_ranges:
                    if len(entry) == 3:
                        b_start, b_end, _ = entry
                    else:
                        b_start, b_end = entry
                        
                    if not (end_min <= b_start or start_min >= b_end):
                        is_free = False
                        break
                
                if is_free:
                    available[room.id][day.id].append({
                        "start_min": start_min,
                        "end_min": end_min,
                        "label": block["label"],
                        "is_lab": block.get("is_lab", False),
                    })
    
    return dict(available)


def get_instructor_availability(
    instructors: List[models.Instructor],
    days: List[models.Day],
    booked_instr_ranges: Dict[Tuple[int, int], List[Tuple[int, int]]],
) -> Dict[int, Dict[int, List[Dict]]]:
    """
    Get free time slots for each instructor on each day.
    
    Args:
        instructors: List of Instructor models
        days: List of Day models
        booked_instr_ranges: Existing bookings {(instructor_id, day_id): [(start_min, end_min), ...]}
    
    Returns:
        {instructor_id: {day_id: [{"start_min": x, "end_min": y, "label": "7:00-8:30"}, ...]}}
    """
    available = defaultdict(lambda: defaultdict(list))
    
    for instructor in instructors:
        for day in days:
            instr_key = (instructor.id, day.id)
            booked_ranges = booked_instr_ranges.get(instr_key, [])
            
            # Check each time block
            for block in TIME_BLOCKS:
                start_min = time_to_minutes(block["start"])
                end_min = time_to_minutes(block["end"])
                
                # Check if this slot overlaps with any booked range
                is_free = True
                for entry in booked_ranges:
                    if len(entry) == 3:
                        b_start, b_end, _ = entry
                    else:
                        b_start, b_end = entry
                        
                    if not (end_min <= b_start or start_min >= b_end):
                        is_free = False
                        break
                
                if is_free:
                    available[instructor.id][day.id].append({
                        "start_min": start_min,
                        "end_min": end_min,
                        "label": block["label"],
                        "is_lab": block.get("is_lab", False),
                    })
    
    return dict(available)


def generate_recommendations(
    subject: models.Subject,
    eligible_room_ids: List[int],
    eligible_instructor_ids: List[int],
    rooms: List[models.Room],
    instructors: List[models.Instructor],
    days: List[models.Day],
    room_availability: Dict[int, Dict[int, List[Dict]]],
    instructor_availability: Dict[int, Dict[int, List[Dict]]],
    student_time_ranges: Dict[Tuple[int, int, str, int], List[Tuple[int, int]]],
    course_id: int,
    year: Optional[int],
    block_label: str = "A",
    max_recommendations: int = 5,
) -> List[Dict]:
    """
    Generate scheduling recommendations for a subject that couldn't be scheduled.
    
    Args:
        subject: The Subject model to schedule
        eligible_room_ids: List of room IDs suitable for this subject
        eligible_instructor_ids: List of instructor IDs who can teach this subject
        rooms: All rooms
        instructors: All instructors
        days: All days
        room_availability: Pre-computed room availability from get_available_slots()
        instructor_availability: Pre-computed instructor availability
        student_time_ranges: Existing student schedule ranges
        course_id: Course ID for student conflict checking
        year: Year level for student conflict checking
        block_label: Student block label (A, B, C, etc.)
        max_recommendations: Maximum number of recommendations to return
    
    Returns:
        List of recommendations, sorted by preference:
        [{"room_id": x, "room_name": "Room 101", "instructor_id": y, 
          "instructor_name": "Prof. X", "day_id": z, "day_label": "M",
          "time": "7:00-8:30", "start_min": 420, "end_min": 510, "score": 100}]
    """
    recommendations = []
    
    room_lookup = {r.id: r for r in rooms}
    instructor_lookup = {i.id: i for i in instructors}
    day_lookup = {d.id: d for d in days}
    
    subj_type = (getattr(subject, "type", "") or "").upper().strip()
    is_lab = subj_type == "LAB"
    
    # For each eligible room, find slots where both room AND an instructor are free
    for room_id in eligible_room_ids:
        room = room_lookup.get(room_id)
        if not room:
            continue
        
        room_slots = room_availability.get(room_id, {})
        
        for day_id, slots in room_slots.items():
            day = day_lookup.get(day_id)
            if not day:
                continue
            
            for slot in slots:
                # For LAB subjects, prefer LAB slots
                if is_lab and not slot.get("is_lab", False):
                    continue
                
                start_min = slot["start_min"]
                end_min = slot["end_min"]
                
                # Check student conflict
                student_key = (course_id, year, block_label, day_id)
                student_ranges = student_time_ranges.get(student_key, [])
                has_student_conflict = False
                for s_start, s_end in student_ranges:
                    if not (end_min <= s_start or start_min >= s_end):
                        has_student_conflict = True
                        break
                
                if has_student_conflict:
                    continue
                
                # Find available instructors for this slot
                for instr_id in eligible_instructor_ids:
                    instructor = instructor_lookup.get(instr_id)
                    if not instructor:
                        continue
                    
                    instr_slots = instructor_availability.get(instr_id, {}).get(day_id, [])
                    
                    # Check if instructor is free at this time
                    instr_free = False
                    for instr_slot in instr_slots:
                        if instr_slot["start_min"] == start_min and instr_slot["end_min"] == end_min:
                            instr_free = True
                            break
                    
                    if instr_free:
                        # Calculate preference score (higher = better)
                        score = 100
                        # Prefer morning slots
                        if start_min < 720:  # Before noon
                            score += 20
                        # Prefer non-evening slots
                        if end_min > 1080:  # After 6 PM
                            score -= 30
                        
                        recommendations.append({
                            "room_id": room_id,
                            "room_name": room.name,
                            "instructor_id": instr_id,
                            "instructor_name": getattr(instructor, "name", f"Instructor {instr_id}"),
                            "day_id": day_id,
                            "day_label": day.label,
                            "time": slot["label"],
                            "start_min": start_min,
                            "end_min": end_min,
                            "score": score,
                            "is_lab_slot": slot.get("is_lab", False),
                        })
    
    # Sort by score (highest first) and limit
    recommendations.sort(key=lambda x: -x["score"])
    return recommendations[:max_recommendations]


def diagnose_scheduling_failure(
    subject: models.Subject,
    eligible_room_ids: List[int],
    eligible_instructor_ids: List[int],
    room_availability: Dict[int, Dict[int, List[Dict]]],
    instructor_availability: Dict[int, Dict[int, List[Dict]]],
    days: List[models.Day],
) -> Dict[str, Any]:
    """
    Diagnose why a subject couldn't be scheduled.
    
    Returns:
        {
            "failure_type": "INSTRUCTOR" | "ROOM" | "NO_SLOTS" | "NO_RESOURCES",
            "available_room_slots_count": int,
            "available_instructor_slots_count": int,
            "details": str
        }
    """
    # Count available slots for eligible rooms
    room_slot_count = 0
    for room_id in eligible_room_ids:
        for day_id, slots in room_availability.get(room_id, {}).items():
            room_slot_count += len(slots)
    
    # Count available slots for eligible instructors
    instr_slot_count = 0
    for instr_id in eligible_instructor_ids:
        for day_id, slots in instructor_availability.get(instr_id, {}).items():
            instr_slot_count += len(slots)
    
    # Determine failure type
    if not eligible_room_ids or not eligible_instructor_ids:
        failure_type = "NO_RESOURCES"
        details = "No eligible rooms or instructors for this subject"
    elif room_slot_count == 0 and instr_slot_count == 0:
        failure_type = "NO_SLOTS"
        details = "All rooms and all instructors are fully booked"
    elif room_slot_count == 0:
        failure_type = "ROOM"
        details = f"All eligible rooms are fully booked ({len(eligible_room_ids)} rooms checked)"
    elif instr_slot_count == 0:
        failure_type = "INSTRUCTOR"
        details = f"All eligible instructors are fully booked ({len(eligible_instructor_ids)} instructors checked)"
    else:
        failure_type = "CONFLICT"
        details = f"Rooms have {room_slot_count} free slots, instructors have {instr_slot_count} free slots, but no matching time found"
    
    return {
        "failure_type": failure_type,
        "available_room_slots_count": room_slot_count,
        "available_instructor_slots_count": instr_slot_count,
        "details": details,
    }
