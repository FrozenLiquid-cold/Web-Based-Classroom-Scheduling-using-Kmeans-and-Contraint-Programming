"""Run migration 015: subject_room_preferences table."""
import os
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from api.db import engine


def migrate():
    migration_file = Path(__file__).resolve().parent / "migrations" / "015_subject_room_preferences.sql"
    sql = migration_file.read_text(encoding="utf-8")

    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(sql))
    print("Migration 015_subject_room_preferences applied successfully.")


if __name__ == "__main__":
    migrate()
