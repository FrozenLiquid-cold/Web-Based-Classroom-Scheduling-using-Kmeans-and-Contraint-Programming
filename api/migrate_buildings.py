from sqlalchemy import inspect, text, Integer, Column, String, Text, ForeignKey, UniqueConstraint
from .db import engine, Base
from .models import Building, BuildingDistance

def ensure_buildings_tables():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.begin() as conn:
        # Create buildings table if not exists
        if "buildings" not in existing_tables:
            print("Creating buildings table...")
            Building.__table__.create(conn)
        
        # Create building_distances table if not exists
        if "building_distances" not in existing_tables:
            print("Creating building_distances table...")
            BuildingDistance.__table__.create(conn)

        # Check Room table for building_id
        room_columns = {col["name"] for col in inspector.get_columns("rooms")}
        if "building_id" not in room_columns:
            print("Adding building_id to rooms table...")
            conn.execute(text("ALTER TABLE rooms ADD COLUMN building_id INTEGER NULL REFERENCES buildings(id)"))
        
    print("Migration successful.")

if __name__ == "__main__":
    ensure_buildings_tables()
