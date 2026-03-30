import logging
import sys
import os
sys.path.append(os.getcwd())
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api import models

# Constants from cp_scheduler.py
NSTP_DAY_LABEL = "SUN"
NSTP_ROOM_NAME = "FIELD"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_path = "postgresql+psycopg2://postgres:ara@localhost:5432/Scheduler_DB"
engine = create_engine(db_path)
Session = sessionmaker(bind=engine)
db = Session()

def verify_env():
    print(f"Checking constants: Day='{NSTP_DAY_LABEL}', Room='{NSTP_ROOM_NAME}'")
    
    # 1. Check Day
    day = db.query(models.Day).filter(models.Day.label == NSTP_DAY_LABEL).first()
    if day:
        print(f"SUCCESS: Found Day '{day.label}' (ID: {day.id})")
    else:
        print(f"FAILURE: Day '{NSTP_DAY_LABEL}' NOT found!")
        days = db.query(models.Day).all()
        print(f"  Available days: {[d.label for d in days]}")

    # 2. Check Room
    room = db.query(models.Room).filter(models.Room.name == NSTP_ROOM_NAME).first()
    if room:
        print(f"SUCCESS: Found Room '{room.name}' (ID: {room.id})")
    else:
        print(f"FAILURE: Room '{NSTP_ROOM_NAME}' NOT found!")
        rooms = db.query(models.Room).limit(10).all()
        print(f"  Sample rooms: {[r.name for r in rooms]}")

    # 3. Check Kim
    instr = db.query(models.Instructor).get(14)
    if instr:
        print(f"Instructor 14: {instr.first_name} {instr.last_name}")
        # Check conflicts assuming semester=1
        conflicts = db.query(models.Schedule).filter(
            models.Schedule.instructor_id == 14,
            models.Schedule.day_id == (day.id if day else -1),
            models.Schedule.semester == 1
        ).all()
        print(f"Conflicts for Sem 1 on Sunday: {len(conflicts)}")
        if conflicts:
            print(f"  -> {[s.time for s in conflicts]}")

if __name__ == "__main__":
    verify_env()
