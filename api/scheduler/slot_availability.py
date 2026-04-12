"""Slot availability analysis and recommendation generation for scheduling."""
from typing import List, Dict, Tuple, Optional, Any, Set
from collections import defaultdict
from sqlalchemy.orm import Session
from api import models
from .timeslots import TIME_BLOCKS, time_to_minutes, minutes_to_time_str


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
    
    For LEC subjects: generates M-W and T-TH paired-day options + Friday single-day.
    For LAB subjects: generates single-day options only.
    
    For paired patterns, checks that the room AND instructor are free on BOTH days
    at the same time, and that no student conflict exists on either day.
    """
    recommendations = []
    
    room_lookup = {r.id: r for r in rooms}
    instructor_lookup = {i.id: i for i in instructors}
    day_lookup = {d.id: d for d in days}
    day_by_label = {d.label.upper(): d for d in days}
    
    subj_type = (getattr(subject, "type", "") or "").upper().strip()
    is_lab = subj_type == "LAB"
    
    # Define day patterns based on subject type
    PAIRED_PATTERNS = [
        ("M-W", ["M", "W"]),
        ("T-TH", ["T", "TH"]),
    ]
    SINGLE_PATTERNS = [("F", ["F"])]
    WEEKDAY_LABELS = {"M", "T", "W", "TH", "F"}
    WEEKEND_LABELS = {"SAT", "SUN"}
    
    if is_lab:
        # LAB: paired M-W / T-TH patterns + single weekdays FIRST, then weekends
        weekday_singles = [(d.label, [d.label]) for d in days if d.label.upper() in WEEKDAY_LABELS]
        weekend_singles = [(d.label, [d.label]) for d in days if d.label.upper() in WEEKEND_LABELS]
        patterns_to_try = PAIRED_PATTERNS + weekday_singles + weekend_singles
    else:
        # LEC: paired M-W / T-TH patterns + Friday single-day
        patterns_to_try = PAIRED_PATTERNS + SINGLE_PATTERNS

    def _check_slot_on_day(room_id, day_id, start_min, end_min):
        """Check if room is free for the given time range on the given day."""
        room_slots = room_availability.get(room_id, {}).get(day_id, [])
        for slot in room_slots:
            # The slot must fully cover the requested range
            if slot["start_min"] <= start_min and slot["end_min"] >= end_min:
                return True
        return False

    def _check_instr_on_day(instr_id, day_id, start_min, end_min):
        """Check if instructor is free for the given time range on the given day."""
        instr_slots = instructor_availability.get(instr_id, {}).get(day_id, [])
        for slot in instr_slots:
            if slot["start_min"] <= start_min and slot["end_min"] >= end_min:
                return True
        return False

    def _check_student_conflict(day_id, start_min, end_min):
        """Check if this timeslot conflicts with existing student schedule."""
        student_key = (course_id, year, block_label, day_id)
        student_ranges = student_time_ranges.get(student_key, [])
        for s_start, s_end in student_ranges:
            if not (end_min <= s_start or start_min >= s_end):
                return True  # conflict found
        return False

    for pattern_label, day_labels in patterns_to_try:
        # Resolve day objects for this pattern
        pattern_days = []
        for dl in day_labels:
            d = day_by_label.get(dl.upper())
            if d:
                pattern_days.append(d)
        
        if len(pattern_days) != len(day_labels):
            continue  # skip if any day not found in DB
        
        is_paired = len(pattern_days) == 2
        
        for room_id in eligible_room_ids:
            room = room_lookup.get(room_id)
            if not room:
                continue
            
            # Use first day's available slots as the candidate time windows
            first_day = pattern_days[0]
            room_slots = room_availability.get(room_id, {}).get(first_day.id, [])
            
            for slot in room_slots:
                # NOTE: Removed is_lab filter — the CP solver schedules LAB subjects
                # in any available timeslot, so recommendations should too.
                
                start_min = slot["start_min"]
                end_min = slot["end_min"]
                
                # For paired patterns, check room availability AND student conflicts
                # on ALL days of the pattern
                all_days_ok = True
                for pd in pattern_days:
                    if not _check_slot_on_day(room_id, pd.id, start_min, end_min):
                        all_days_ok = False
                        break
                    if _check_student_conflict(pd.id, start_min, end_min):
                        all_days_ok = False
                        break
                
                if not all_days_ok:
                    continue
                
                # Find an instructor who is free on ALL days at this time
                for instr_id in eligible_instructor_ids:
                    instructor = instructor_lookup.get(instr_id)
                    if not instructor:
                        continue
                    
                    instr_ok = True
                    for pd in pattern_days:
                        if not _check_instr_on_day(instr_id, pd.id, start_min, end_min):
                            instr_ok = False
                            break
                    
                    if not instr_ok:
                        continue
                    
                    # Calculate preference score (higher = better)
                    score = 100
                    if start_min < 720:   # Before noon
                        score += 20
                    if end_min > 1080:    # After 6 PM
                        score -= 30
                    if is_paired:
                        score += 10       # Prefer proper paired patterns over single-day
                    
                    # CRITICAL: Heavily penalize weekend days so weekday slots
                    # are always preferred when available
                    day_label_upper = pattern_label.upper()
                    if day_label_upper == "SAT":
                        score -= 200
                    elif day_label_upper == "SUN":
                        score -= 300
                    
                    day_ids = [pd.id for pd in pattern_days]
                    
                    instr_name = f"{instructor.first_name} {instructor.last_name}" if getattr(instructor, 'last_name', None) else getattr(instructor, 'first_name', f"Instructor {instr_id}")
                    recommendations.append({
                        "room_id": room_id,
                        "room_name": room.name,
                        "instructor_id": instr_id,
                        "instructor_name": instr_name,
                        "day_id": pattern_days[0].id,
                        "day_ids": day_ids,
                        "day_label": pattern_label,
                        "time": f"{minutes_to_time_str(start_min)} - {minutes_to_time_str(end_min)}",
                        "start_min": start_min,
                        "end_min": end_min,
                        "score": score,
                        "is_lab_slot": slot.get("is_lab", False),
                        "is_paired": is_paired,
                    })
    
    # Deduplicate: keep top N instructors per unique (room, pattern, time) slot.
    # Previously only kept the "best" instructor, which caused all recommendations
    # to use the same instructor — if that instructor had a cross-block conflict,
    # every recommendation was rejected and the subject stayed unscheduled.
    MAX_INSTRUCTORS_PER_SLOT = 3
    slot_groups = {}
    for rec in recommendations:
        slot_key = (rec["room_id"], rec["day_label"], rec["start_min"], rec["end_min"])
        if slot_key not in slot_groups:
            slot_groups[slot_key] = []
        slot_groups[slot_key].append(rec)
    
    deduped = []
    for slot_key, recs in slot_groups.items():
        # Sort by score descending, keep top N instructors per slot
        recs.sort(key=lambda x: -x["score"])
        # Deduplicate by instructor within this slot
        seen_instructors = set()
        for rec in recs:
            if rec["instructor_id"] not in seen_instructors:
                deduped.append(rec)
                seen_instructors.add(rec["instructor_id"])
                if len(seen_instructors) >= MAX_INSTRUCTORS_PER_SLOT:
                    break
    
    # Sort by score (highest first) and limit
    deduped.sort(key=lambda x: -x["score"])
    
    # Allow up to 15 alternatives for better cross-block conflict resolution
    actual_max = max(max_recommendations, 15)
    return deduped[:actual_max]


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
