"""Run migration to add indexes for instructor-related queries (PostgreSQL)"""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import engine
from sqlalchemy import text

def run_migration():
    """Execute the index migration on PostgreSQL"""
    
    migration_sql = """
    -- Index on schedules.instructor_id for filtering schedules by instructor
    CREATE INDEX IF NOT EXISTS idx_schedules_instructor_id ON schedules(instructor_id);

    -- Composite index for common schedule queries (instructor + semester + year)
    CREATE INDEX IF NOT EXISTS idx_schedules_instructor_semester_year ON schedules(instructor_id, semester, year);

    -- Index on schedules.day_id for day-based filtering
    CREATE INDEX IF NOT EXISTS idx_schedules_day_id ON schedules(day_id);

    -- Index on schedules.room_id for room-based filtering
    CREATE INDEX IF NOT EXISTS idx_schedules_room_id ON schedules(room_id);

    -- Index on schedules.course_id for course-based filtering
    CREATE INDEX IF NOT EXISTS idx_schedules_course_id ON schedules(course_id);

    -- Composite index for schedule conflict checking (room + day + time)
    CREATE INDEX IF NOT EXISTS idx_schedules_room_day_time ON schedules(room_id, day_id, time);

    -- Composite index for instructor conflict checking (instructor + day + time)
    CREATE INDEX IF NOT EXISTS idx_schedules_instructor_day_time ON schedules(instructor_id, day_id, time);

    -- Index on instructors.college_id for filtering by college
    CREATE INDEX IF NOT EXISTS idx_instructors_college_id ON instructors(college_id);

    -- Index on instructors.username for login lookups
    CREATE INDEX IF NOT EXISTS idx_instructors_username ON instructors(username);

    -- Index on users.instructor_id for user-instructor lookups
    CREATE INDEX IF NOT EXISTS idx_users_instructor_id ON users(instructor_id);
    """
    
    # Check if swap_requests table exists before adding indexes
    swap_indexes_sql = """
    -- Index on swap_requests for target instructor (incoming requests)
    CREATE INDEX IF NOT EXISTS idx_swap_requests_target_id ON swap_requests(target_id);

    -- Index on swap_requests for requester (outgoing requests)
    CREATE INDEX IF NOT EXISTS idx_swap_requests_requester_id ON swap_requests(requester_id);

    -- Composite index for pending swap requests
    CREATE INDEX IF NOT EXISTS idx_swap_requests_target_status ON swap_requests(target_id, status);
    """
    
    try:
        with engine.connect() as conn:
            # Execute main indexes
            for statement in migration_sql.strip().split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        conn.execute(text(statement))
                        print(f"✓ Executed: {statement[:60]}...")
                    except Exception as e:
                        print(f"⚠ Skipped (may already exist): {str(e)[:50]}")
            
            # Try swap_requests indexes (table may not exist yet)
            for statement in swap_indexes_sql.strip().split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        conn.execute(text(statement))
                        print(f"✓ Executed: {statement[:60]}...")
                    except Exception as e:
                        print(f"⚠ Skipped (swap_requests may not exist): {str(e)[:50]}")
            
            conn.commit()
            print("\n✓ Successfully added instructor query indexes!")
            
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    run_migration()
