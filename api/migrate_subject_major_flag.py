from sqlalchemy import inspect, text

from .db import engine


def ensure_subject_major_flag():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("subjects")}

    with engine.begin() as conn:
        if "is_major" not in columns:
            conn.execute(text("ALTER TABLE subjects ADD COLUMN is_major BOOLEAN NULL"))


if __name__ == "__main__":
    ensure_subject_major_flag()
