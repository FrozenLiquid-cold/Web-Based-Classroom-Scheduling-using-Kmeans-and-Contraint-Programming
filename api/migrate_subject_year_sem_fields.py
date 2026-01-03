from sqlalchemy import inspect, text

from .db import engine


def ensure_subject_year_sem_fields():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("subjects")}

    with engine.begin() as conn:
        if "year_level" not in columns:
            conn.execute(text("ALTER TABLE subjects ADD COLUMN year_level INTEGER NULL"))
        if "semester" not in columns:
            conn.execute(text("ALTER TABLE subjects ADD COLUMN semester INTEGER NULL"))


if __name__ == "__main__":
    ensure_subject_year_sem_fields()
