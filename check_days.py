
from api.db import SessionLocal
from api import models

db = SessionLocal()
days = db.query(models.Day).all()
print("Days in DB:")
for d in days:
    print(f"ID: {d.id}, Label: '{d.label}'")

rooms = db.query(models.Room).all()
print("Rooms in DB:")
for r in rooms:
    print(f"ID: {r.id}, Name: '{r.name}'")

db.close()
