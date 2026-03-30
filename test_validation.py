import sys
from pathlib import Path
import os
import requests
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up path to import api
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

try:
    from api.db import SessionLocal
    from api import models
    db = SessionLocal()
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# Base URL for API
BASE_URL = "http://localhost:8000"  # Assuming running locally? Or verify from test_schedule.py output?
# test_schedule.py said Base URL: http://127.0.0.1:8000

# 1. Create a dummy conflict using existing Course 3/Subject 113
# Room 15, Monday, 8:00-9:00
print("Creating dummy conflict...")
conflict_sched = models.Schedule(
    course_id=3,     # Existing Course
    subject_id=113,  # Existing Subject
    room_id=15,      # GS ER 7
    day_id=1,        # Monday
    time="8:00-9:00",
    semester=1,
    year=1,
    block="A"
)
db.add(conflict_sched)
db.commit()
print(f"Created conflict ID {conflict_sched.id}")

try:
    # 2. Call Validation Endpoint
    # Validate a new booking for Room 15, Monday, 8:30-9:30 (Overlap)
    payload = {
        "room_id": 15,
        "day_id": 1,
        "start_time": "08:30",
        "end_time": "09:30",
        "semester": 1,
        "year": 1,
        "course_id": 4, # Our target course
        "block": "A"
    }
    
    # We call the validation function directly if possible to avoid HTTP overhead/server dependency
    # But validation.py is a blueprint...
    # We can import it?
    
    from api.routes.validation import validate_schedule_item
    # But allow Flask context?
    # It uses request.get_json().
    # Easier to use 'requests' against running server.
    
    print("Calling validation endpoint...")
    resp = requests.post(f"{BASE_URL}/api/validate/schedule-item", json=payload)
    if resp.status_code == 200:
        print("Response:", json.dumps(resp.json(), indent=2))
    else:
        print(f"Error {resp.status_code}: {resp.text}")

finally:
    # 3. Cleanup
    print("Cleaning up...")
    db.delete(conflict_sched)
    db.commit()
    db.close()
