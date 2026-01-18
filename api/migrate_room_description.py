from sqlalchemy import inspect, text
from .db import engine

def ensure_room_description_field():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("rooms")}

    with engine.begin() as conn:
        if "description" not in columns:
            print("Adding description column to rooms table...")
            conn.execute(text("ALTER TABLE rooms ADD COLUMN description TEXT NULL"))
            print("Migration successful.")
        else:
            print("Column 'description' already exists in rooms table.")

if __name__ == "__main__":
    ensure_room_description_field()
