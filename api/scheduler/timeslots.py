"""Time slot management utilities"""
import re
from typing import List, Dict, Tuple
from datetime import time

# Registrar-provided time windows (shared across all days)
TIME_BLOCKS = [
    {"label": "7:00–8:30", "start": "07:00", "end": "08:30", "is_lab": False},
    {"label": "7:30–8:30", "start": "07:30", "end": "08:30", "is_lab": False},
    {"label": "7:30–9:00", "start": "07:30", "end": "09:00", "is_lab": True},
    {"label": "8:00–9:00", "start": "08:00", "end": "09:00", "is_lab": False},
    {"label": "8:30–10:00", "start": "08:30", "end": "10:00", "is_lab": False},
    {"label": "9:00–10:00", "start": "09:00", "end": "10:00", "is_lab": False},
    {"label": "9:00–10:30", "start": "09:00", "end": "10:30", "is_lab": True},
    {"label": "9:00–12:00", "start": "09:00", "end": "12:00", "is_lab": False},
    {"label": "10:30–11:30", "start": "10:30", "end": "11:30", "is_lab": False},
    {"label": "10:30–12:00", "start": "10:30", "end": "12:00", "is_lab": True},
    {"label": "11:00–12:00", "start": "11:00", "end": "12:00", "is_lab": False},
    {"label": "1:00–2:00", "start": "13:00", "end": "14:00", "is_lab": False},
    {"label": "1:00–2:30", "start": "13:00", "end": "14:30", "is_lab": False},
    {"label": "1:00–3:00", "start": "13:00", "end": "15:00", "is_lab": False},
    {"label": "2:00–3:00", "start": "14:00", "end": "15:00", "is_lab": False},
    {"label": "2:30–4:00", "start": "14:30", "end": "16:00", "is_lab": True},
    {"label": "3:00–5:00", "start": "15:00", "end": "17:00", "is_lab": False},
    {"label": "4:00–5:30", "start": "16:00", "end": "17:30", "is_lab": True},
    {"label": "5:30–7:00", "start": "17:30", "end": "19:00", "is_lab": False},
]



def time_to_minutes(time_str: str) -> int:
    """Convert time string to minutes since midnight"""
    if not time_str:
        return 0
    
    time_str = str(time_str).strip()
    
    # Try parsing HH:MM format
    try:
        if ":" in time_str:
            parts = time_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1]) if len(parts) > 1 else 0
            return hours * 60 + minutes
    except:
        pass
    
    # Try regex parsing
    m = re.search(r"(\d{1,2}):(\d{2})", time_str)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        # Handle AM/PM if present
        if re.search(r"pm", time_str, re.IGNORECASE) and hours < 12:
            hours += 12
        if re.search(r"am", time_str, re.IGNORECASE) and hours == 12:
            hours = 0
        return hours * 60 + minutes
    
    return 0


def get_time_block_minutes(block: Dict) -> Tuple[int, int]:
    """Get start and end minutes for a time block"""
    start_min = time_to_minutes(block["start"])
    end_min = time_to_minutes(block["end"])
    return start_min, end_min


def is_consecutive_blocks(block_indices: List[int]) -> bool:
    """Check if time block indices are consecutive"""
    if len(block_indices) < 2:
        return True
    
    for i in range(len(block_indices) - 1):
        curr_idx = block_indices[i]
        next_idx = block_indices[i + 1]
        
        # Get end time of current block and start time of next block
        curr_end = time_to_minutes(TIME_BLOCKS[curr_idx]["end"])
        next_start = time_to_minutes(TIME_BLOCKS[next_idx]["start"])
        
        if curr_end != next_start:
            return False
    
    return True


def create_time_slots_for_day(day_label: str) -> List[Dict]:
    """Create time slots for a specific day"""
    slots = []
    for idx, block in enumerate(TIME_BLOCKS):
        slots.append({
            "day": day_label,
            "index": idx,
            "label": block["label"],
            "start": block["start"],
            "end": block["end"],
            "start_min": time_to_minutes(block["start"]),
            "end_min": time_to_minutes(block["end"]),
            "is_lab": block.get("is_lab", False),
        })
    return slots



def get_all_time_slots(days: List[str]) -> List[Dict]:
    """Get all time slots for all days"""
    all_slots = []
    for day in days:
        day_slots = create_time_slots_for_day(day)
        all_slots.extend(day_slots)
    return all_slots

# Function expected by scheduler.py to return Dict[str, List[Dict]]
def get_slots_by_day(days: List[str]) -> Dict[str, Dict]:
    """
    Get time slots for multiple days, returned as a dictionary:
    { "DayLabel": [slots...] }
    """
    return {day: create_time_slots_for_day(day) for day in days}

