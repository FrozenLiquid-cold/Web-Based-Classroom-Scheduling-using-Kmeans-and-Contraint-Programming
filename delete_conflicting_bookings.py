import sys
from pathlib import Path
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up path to import api
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

try:
    from api.db import SessionLocal
    # Ensure models are imported so they are registered
    from api import models
    db = SessionLocal()
except ImportError as e:
    print(f"Import Error: {e}")
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

ids_to_delete = [
    11517, # M 7:00-8:30 (Subj 113)
    11518, # W 7:00-8:30 (Subj 113)
    11545, # M 8:30-10:00 (Subj 115)
    11546, # W 8:30-10:00 (Subj 115)
]

print(f"Attempting to delete {len(ids_to_delete)} conflicting schedules for Course 3...")
count = 0
for sid in ids_to_delete:
    sched = db.query(models.Schedule).filter(models.Schedule.id == sid).first()
    if sched:
        print(f"Deleting ID {sid}: {sched.time} (Subj {sched.subject_id} Course {sched.course_id})")
        db.delete(sched)
        count += 1
    else:
        print(f"ID {sid} not found.")

db.commit()
print(f"Deleted {count} schedules.")
db.close()
