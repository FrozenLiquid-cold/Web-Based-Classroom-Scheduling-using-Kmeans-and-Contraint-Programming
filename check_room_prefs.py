import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api'))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api'))

from api.db import SessionLocal
from api.models import BuildingDistance, Building, Room

db = SessionLocal()

print("=== Buildings ===")
bldgs = db.query(Building).all()
for b in bldgs:
    print(f"  id={b.id}, name='{b.name}', is_shared={b.is_shared}, college_id={b.college_id}")

print(f"\n=== Building Distances ({db.query(BuildingDistance).count()} total) ===")
dists = db.query(BuildingDistance).all()
for d in dists:
    fb = db.query(Building).get(d.from_building_id)
    tb = db.query(Building).get(d.to_building_id)
    print(f"  {fb.name if fb else '?'} -> {tb.name if tb else '?'}: {d.travel_time_minutes} min")

print("\n=== Room -> Building mapping ===")
rooms = db.query(Room).all()
for r in rooms:
    bldg = db.query(Building).get(r.building_id) if r.building_id else None
    print(f"  room_id={r.id}, name='{r.name}', building='{bldg.name if bldg else 'NONE'}' (building_id={r.building_id})")

db.close()
