"""Migration script to restore the `capacity` column on rooms and fill nulls with 0."""

from sqlalchemy import inspect, text

from .db import engine


def ensure_capacity_column():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("rooms")}
    with engine.begin() as conn:
        if "capacity" not in columns:
            conn.execute(
                text("ALTER TABLE rooms ADD COLUMN capacity INTEGER DEFAULT 0")
            )
            print("[ADDED] `capacity` column to rooms (default 0).")
        else:
            print("[INFO] `capacity` column already exists on rooms.")

        conn.execute(text("UPDATE rooms SET capacity = 0 WHERE capacity IS NULL"))
        print("[UPDATED] Normalized existing room rows to capacity = 0 (where null).")


def ensure_schedule_subject_nullable():
    """Ensure `schedules.subject_id` allows NULL values for course-level blocks."""
    inspector = inspect(engine)
    subject_column = None
    for column in inspector.get_columns("schedules"):
        if column["name"] == "subject_id":
            subject_column = column
            break

    if subject_column is None:
        print("! `subject_id` column not found on schedules; skipping nullability check.")
        return

    if subject_column.get("nullable", True):
        print("~ `schedules.subject_id` already nullable.")
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE schedules ALTER COLUMN subject_id DROP NOT NULL"))
        print("✓ Relaxed NOT NULL constraint on `schedules.subject_id`.")


if __name__ == "__main__":
    ensure_capacity_column()
    ensure_schedule_subject_nullable()

