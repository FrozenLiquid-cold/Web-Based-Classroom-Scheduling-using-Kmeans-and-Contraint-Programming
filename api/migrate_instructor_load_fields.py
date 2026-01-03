"""Migration script to add employment_type and designation fields to instructors."""

from sqlalchemy import inspect, text

from .db import engine


def ensure_instructor_load_fields():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("instructors")}

    with engine.begin() as conn:
        if "employment_type" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE instructors ADD COLUMN employment_type VARCHAR(20) NULL"
                )
            )
        if "designation" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE instructors ADD COLUMN designation VARCHAR(100) NULL"
                )
            )


if __name__ == "__main__":
    ensure_instructor_load_fields()
