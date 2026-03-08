"""
Migration: Add lec_hours and lab_hours columns to curriculum_subjects table.
Uses the app's own SQLAlchemy engine so credentials are always correct.
"""
import sys
import os

# Add project root to path so we can import the api package
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from api.db import engine


def migrate():
    with engine.connect() as conn:
        # Check existing columns
        result = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'curriculum_subjects'
        """))
        columns = [row[0] for row in result.fetchall()]

        if not columns:
            print("curriculum_subjects table not found! Start the API server first to create tables.")
            return

        if "lec_hours" not in columns:
            conn.execute(text("ALTER TABLE curriculum_subjects ADD COLUMN lec_hours INTEGER DEFAULT 0"))
            print("Added lec_hours column")
        else:
            print("lec_hours column already exists")

        if "lab_hours" not in columns:
            conn.execute(text("ALTER TABLE curriculum_subjects ADD COLUMN lab_hours INTEGER DEFAULT 0"))
            print("Added lab_hours column")
        else:
            print("lab_hours column already exists")

        conn.commit()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
