
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path.cwd()))

from api.scheduler.timeslots import time_to_minutes, TIME_BLOCKS, create_time_slots_for_day

print("Testing time_to_minutes:")
print(f"Empty string: {time_to_minutes('')}")
print(f"None: {time_to_minutes(None)}")
print(f"'07:00': {time_to_minutes('07:00')}")
print(f"'7:00': {time_to_minutes('7:00')}")
print(f"'00:00': {time_to_minutes('00:00')}")

print("\nChecking TIME_BLOCKS:")
for i, block in enumerate(TIME_BLOCKS):
    start = block.get("start")
    start_min = time_to_minutes(start)
    print(f"Block {i}: start='{start}', start_min={start_min}")

print("\nChecking create_time_slots_for_day('M'):")
slots = create_time_slots_for_day('M')
for i, slot in enumerate(slots):
    print(f"Slot {i}: start='{slot['start']}', start_min={slot['start_min']}")
