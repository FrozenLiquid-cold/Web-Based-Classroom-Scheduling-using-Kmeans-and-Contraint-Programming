"""Greedy scheduler algorithm (fallback when OR-Tools is not available)"""
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict
from api import models
from .timeslots import TIME_BLOCKS, time_to_minutes


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Check if two time ranges overlap"""
    return not (a_end <= b_start or b_end <= a_start)


def _range_conflicts(
    booked_ranges: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]],
    resource_key: Any,
    day_id: int,
    start_min: int,
    end_min: int
) -> bool:
    """Check if a proposed time range conflicts with any booked ranges"""
    if booked_ranges is None:
        return False
    ranges = booked_ranges.get((resource_key, day_id), [])
    for b_start, b_end in ranges:
        if _ranges_overlap(start_min, end_min, b_start, b_end):
            return True
    return False


def run_greedy_scheduler(
    subjects: List[models.Subject],
    instructors: List[models.Instructor],
    rooms: List[models.Room],
    days: List[models.Day],
    booked_room_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
    booked_instr_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
) -> List[Dict]:
    """
    Generate schedule using greedy algorithm (fallback when CP solver fails)
    
    Args:
        subjects: List of Subject models
        instructors: List of Instructor models
        rooms: List of Room models
        days: List of Day models
        booked_room_ranges_global: Pre-existing room bookings {(room_name, day_id): [(start_min, end_min), ...]}
        booked_instr_ranges_global: Pre-existing instructor bookings {(instr_id, day_id): [(start_min, end_min), ...]}
    
    Returns:
        List of schedule items (dicts with subject_id, instructor_id, room_id, day_id, time)
    """
    if not subjects or not instructors or not rooms or not days:
        return []
    
    # Initialize mutable copies of global bookings for tracking within this run
    room_ranges = defaultdict(list)
    instr_ranges = defaultdict(list)
    
    if booked_room_ranges_global:
        for key, ranges in booked_room_ranges_global.items():
            room_ranges[key].extend(ranges)
    
    if booked_instr_ranges_global:
        for key, ranges in booked_instr_ranges_global.items():
            instr_ranges[key].extend(ranges)
    
    # Build room name lookup
    room_id_to_name = {r.id: r.name for r in rooms}
    
    # Greedy placement algorithm
    schedule = []
    used = set()  # Keys: (day_id, time_idx, room_id) and (day_id, time_idx, instructor_id)
    
    for subject in subjects:
        placed = False
        
        for day in days:
            if placed:
                break
            for time_idx, block in enumerate(TIME_BLOCKS):
                if placed:
                    break
                
                # Get time range for this block
                start_min = time_to_minutes(block["start"])
                end_min = time_to_minutes(block["end"])
                
                # Prefer room type matching subject type
                candidates = [
                    r for r in rooms
                    if (subject.type == "LAB" and r.type == "LAB") or
                       (subject.type == "LEC" and r.type == "LEC")
                ]
                room_list = candidates if candidates else rooms
                
                for room in room_list:
                    if placed:
                        break
                    
                    room_name = room_id_to_name.get(room.id, f"Room_{room.id}")
                    room_key = (day.id, time_idx, room.id)
                    
                    # Check local used set
                    if room_key in used:
                        continue
                    
                    # Check global room ranges (existing bookings from other runs)
                    if _range_conflicts(room_ranges, room_name, day.id, start_min, end_min):
                        continue
                    
                    for instructor in instructors:
                        inst_key = (day.id, time_idx, instructor.id)
                        
                        # Check local used set
                        if inst_key in used:
                            continue
                        
                        # Check global instructor ranges
                        if _range_conflicts(instr_ranges, instructor.id, day.id, start_min, end_min):
                            continue
                        
                        # Found valid slot!
                        used.add(room_key)
                        used.add(inst_key)
                        
                        # Update local tracking ranges
                        room_ranges[(room_name, day.id)].append((start_min, end_min))
                        instr_ranges[(instructor.id, day.id)].append((start_min, end_min))
                        
                        schedule.append({
                            "subject_id": subject.id,
                            "day_id": day.id,
                            "time": block["label"],
                            "room_id": room.id,
                            "instructor_id": instructor.id,
                            "start_min": start_min,
                            "end_min": end_min,
                        })
                        placed = True
                        break
        
        if not placed:
            # Add unplaced subject
            schedule.append({
                "subject_id": subject.id,
                "day_id": None,
                "time": None,
                "room_id": None,
                "instructor_id": None,
            })
    
    return schedule
