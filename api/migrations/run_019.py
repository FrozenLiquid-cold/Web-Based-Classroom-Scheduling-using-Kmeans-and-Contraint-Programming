"""Add course_id to instructor unique constraint for NSTP instructor sharing"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_sy"))
    conn.execute(text("ALTER TABLE schedules DROP CONSTRAINT IF EXISTS uq_instructor_time_block"))
    conn.execute(text("""
        ALTER TABLE schedules ADD CONSTRAINT uq_instructor_time_sy
        UNIQUE (instructor_id, day_id, "time", year, semester, school_year, block, course_id)
    """))
    conn.commit()
    print("Instructor constraint updated: now includes course_id for NSTP sharing")
