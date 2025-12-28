"""Add block_id column to subjects table if it does not already exist."""
from sqlalchemy import inspect, text
from db import engine


def add_block_id_column():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("subjects")}
    if "block_id" in columns:
        print("[OK] subjects.block_id already exists")
        return

    with engine.begin() as conn:
        print("[MIGRATION] Adding block_id column to subjects table...")
        conn.execute(
            text("ALTER TABLE subjects ADD COLUMN block_id VARCHAR(50)")
        )
        print("[DONE] block_id column added.")


if __name__ == "__main__":
    add_block_id_column()

