
import sys
import os
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api.db import SessionLocal
from api import models

def check_db():
    db = SessionLocal()
    try:
        # Check for Course 4 schedules
        schedules = db.query(models.Schedule).filter(models.Schedule.course_id == 4).all()
        print(f"Total schedules for Course 4: {len(schedules)}")
        
        # Breakdown by year and semester
        stats = {}
        for s in schedules:
            key = (s.year, s.semester)
            stats[key] = stats.get(key, 0) + 1
            
        print("Breakdown (Year, Semester): Count")
        for key, count in sorted(stats.items()):
            print(f"  {key}: {count}")
            
        # Check specific items for Year 2
        print("\nSample entries for Course 4 Year 2:")
        y2_schedules = [s for s in schedules if s.year == 2]
        for s in y2_schedules[:10]:
            print(f"  ID={s.id}, Sem={s.semester}, Day={s.day_id}, Time={s.time}, Block={s.block}, Subj={s.subject_id}")
            
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
