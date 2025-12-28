"""Greedy scheduler algorithm (fallback when OR-Tools is not available)"""
from typing import List, Dict
from api import models
from .timeslots import TIME_BLOCKS


def run_greedy_scheduler(
    subjects: List[models.Subject],
    instructors: List[models.Instructor],
    rooms: List[models.Room],
    days: List[models.Day]
) -> List[Dict]:
    """
    Generate schedule using greedy algorithm (matches frontend logic)
    
    Args:
        subjects: List of Subject models
        instructors: List of Instructor models
        rooms: List of Room models
        days: List of Day models
    
    Returns:
        List of schedule items (dicts with subject_id, instructor_id, room_id, day_id, time)
    """
    if not subjects or not instructors or not rooms or not days:
        return []
    
    # Greedy placement algorithm (matches frontend logic)
    schedule = []
    used = set()  # Keys: (day_id, time_idx, room_id) and (day_id, time_idx, instructor_id)
    instructor_idx = 0
    room_idx = 0
    day_idx = 0
    
    for subject in subjects:
        placed = False
        max_tries = len(days) * len(TIME_BLOCKS) * len(rooms)
        
        for tries in range(max_tries):
            day = days[day_idx % len(days)]
            time_idx = tries % len(TIME_BLOCKS)
            
            # Prefer room type matching subject type
            candidates = [
                r for r in rooms
                if (subject.type == "LAB" and r.type == "LAB") or
                   (subject.type == "LEC" and r.type == "LEC")
            ]
            room_list = candidates if candidates else rooms
            room = room_list[room_idx % len(room_list)]
            instructor = instructors[instructor_idx % len(instructors)]
            
            room_key = (day.id, time_idx, room.id)
            inst_key = (day.id, time_idx, instructor.id)
            
            if room_key not in used and inst_key not in used:
                used.add(room_key)
                used.add(inst_key)
                
                schedule.append({
                    "subject_id": subject.id,
                    "day_id": day.id,
                    "time": TIME_BLOCKS[time_idx]["label"],
                    "room_id": room.id,
                    "instructor_id": instructor.id,
                })
                placed = True
                break
            
            room_idx += 1
            instructor_idx += 1
        
        day_idx += 1
        
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

