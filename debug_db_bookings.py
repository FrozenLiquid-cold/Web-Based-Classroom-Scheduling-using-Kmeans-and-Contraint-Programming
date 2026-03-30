import sys
from pathlib import Path
import os

# Set up path to import api
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api import models


# Connect to DB
# Assuming sqlite for now based on context, or using get_db logic?
# I'll use _get_session from api/routes/schedule.py logic or just imports.
# The user's startup command usually sets up DB.
# I'll try to use the existing database.py connection.

try:
    from api.db import SessionLocal
    # Ensure models are imported so they are registered
    from api import models
    db = SessionLocal()
except ImportError as e:
    print(f"Import Error: {e}")
    print("Could not import SessionLocal. Trying to find DB file...")
    # Fallback to sqlite file if standard import fails
    db_path = "scheduler.db"
    if os.path.exists(db_path):
        from sqlalchemy import create_engine
        engine = create_engine(f"sqlite:///{db_path}")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
    else:
        print("Cannot find DB.")
        sys.exit(1)

print("Searching for GS ER 7 bookings...")

# Find Room 15
room = db.query(models.Room).filter(models.Room.name == "GS ER 7").first()
if not room:
    # Try ID 15
    room = db.query(models.Room).filter(models.Room.id == 15).first()

if not room:
    print("Room 15 / GS ER 7 not found in DB.")
else:
    print(f"Room found: {room.name} (ID {room.id})")

    # Query schedules
    schedules = db.query(models.Schedule).filter(models.Schedule.room_id == room.id).all()
    
    print(f"Found {len(schedules)} total schedules for this room.")
    
    for sched in schedules:
        print(f"[ID {sched.id}] Course={sched.course_id} Year={sched.year} Subj={sched.subject_id} Day={sched.day_id} Time='{sched.time}'")

    # Specifically check for Monday (Day 1)
    monday_scheds = [s for s in schedules if s.day_id == 1]
    print(f"\nMonday Bookings ({len(monday_scheds)}):")
    for s in monday_scheds:
        print(f"  - [ID {s.id}] Course={s.course_id} Year={s.year} Time='{s.time}'")

db.close()
