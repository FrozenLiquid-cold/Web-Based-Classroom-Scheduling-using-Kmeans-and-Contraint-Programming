"""Quick test: verify build_eligibility_maps excludes FIELD for CC 102."""
import sys
sys.path.insert(0, ".")
from api.db import SessionLocal
from api import models

db = SessionLocal()

# Get BSCS subjects for year 1, semester 1
course_id = 4  # BSCS
subjects = db.query(models.Subject).filter(
    models.Subject.course_id == course_id,
    models.Subject.year_level == 1,
    models.Subject.semester == 1
).all()
print(f"Subjects for BSCS Y1S1: {len(subjects)}")
for s in subjects:
    print(f"  id={s.id} code={s.code} type={s.type}")

rooms = db.query(models.Room).all()
instructors = db.query(models.Instructor).filter(models.Instructor.is_active == True).all()

from api.scheduler.cp_scheduler import build_eligibility_maps
course_to_instructors, course_to_all_rooms, course_to_preferred_rooms = build_eligibility_maps(subjects, instructors, rooms, db)

# Check CC 102 LEC (id=7) eligible rooms
for s in subjects:
    if "CC 102" in (s.code or ""):
        eligible = course_to_all_rooms.get(s.id, [])
        print(f"\n{s.code} ({s.type}) id={s.id}: {len(eligible)} eligible rooms")
        for rid in eligible:
            r = next((r for r in rooms if r.id == rid), None)
            print(f"  Room id={rid} name={r.name if r else '?'}")
        if 17 in eligible:
            print("  *** FIELD (17) IS IN ELIGIBLE - BUG! ***")
        else:
            print("  ✓ FIELD (17) correctly excluded")

db.close()
