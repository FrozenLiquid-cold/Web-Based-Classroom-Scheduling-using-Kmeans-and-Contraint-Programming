"""
Migration: Add college_id to buildings table.

This links each building to a college, so the scheduler can filter rooms
by college — only assigning rooms from the same college's buildings.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import text
from api.db import SessionLocal


def run_migration():
    db = SessionLocal()
    try:
        conn = db.connection()

        # Check if column already exists
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'buildings' AND column_name = 'college_id'"
        ))
        if result.fetchone():
            print("Column 'college_id' already exists in 'buildings' table. Skipping.")
            return

        print("Adding college_id column to buildings table...")
        conn.execute(text(
            "ALTER TABLE buildings ADD COLUMN college_id INTEGER NULL "
            "REFERENCES colleges(id)"
        ))
        db.commit()
        print("Migration complete: college_id added to buildings table.")
        print()
        print("NEXT STEP: Assign each building to its college via the Buildings management page.")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
