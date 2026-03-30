"""
Script to check for room double-bookings in the database
"""
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api.db import SessionLocal
from api import models
from collections import defaultdict

def check_room_conflicts():
    db = SessionLocal()
    try:
        # Get all schedules
        schedules = db.query(models.Schedule).all()
        print(f"Total schedules in database: {len(schedules)}")
        
        # Get room names
        rooms = {r.id: r.name for r in db.query(models.Room).all()}
        
        # Get day labels
        days = {d.id: d.label for d in db.query(models.Day).all()}
        
        # Get subject codes
        subjects = {s.id: s.code for s in db.query(models.Subject).all()}
        
        # Group by (room_id, day_id, time)
        room_time_groups = defaultdict(list)
        for s in schedules:
            if s.room_id and s.day_id and s.time:
                key = (s.room_id, s.day_id, s.time)
                room_time_groups[key].append(s)
        
        # Find conflicts
        conflicts = []
        for (room_id, day_id, time), items in room_time_groups.items():
            if len(items) > 1:
                conflicts.append({
                    "room_id": room_id,
                    "room_name": rooms.get(room_id, "Unknown"),
                    "day_id": day_id,
                    "day_label": days.get(day_id, "Unknown"),
                    "time": time,
                    "items": items
                })
        
        print(f"\n{'='*80}")
        print(f"ROOM DOUBLE-BOOKINGS FOUND: {len(conflicts)}")
        print(f"{'='*80}")
        
        for conflict in conflicts:
            print(f"\n** CONFLICT: Room '{conflict['room_name']}' (ID: {conflict['room_id']})")
            print(f"   Day: {conflict['day_label']} (ID: {conflict['day_id']})")
            print(f"   Time: {conflict['time']}")
            print(f"   Conflicting schedules ({len(conflict['items'])}):")
            for item in conflict['items']:
                subject_code = subjects.get(item.subject_id, "Unknown")
                print(f"     - ID {item.id}: Subject {subject_code} (ID: {item.subject_id}), "
                      f"Block: {item.block}, Instructor ID: {item.instructor_id}, "
                      f"Year: {item.year}, Semester: {item.semester}")
        
        # Also check for the specific conflicts mentioned
        print(f"\n{'='*80}")
        print("CHECKING SPECIFIC CONFLICTS MENTIONED BY USER:")
        print(f"{'='*80}")
        
        # Find CC 101 and CS Prof Elect 1 subjects
        cc101 = db.query(models.Subject).filter(models.Subject.code.ilike("%CC 101%")).all()
        cs_prof_elect_1 = db.query(models.Subject).filter(models.Subject.code.ilike("%CS Prof Elect 1%")).all()
        
        print(f"\nCC 101 subjects found: {len(cc101)}")
        for s in cc101:
            print(f"  ID: {s.id}, Code: {s.code}, Type: {s.type}, Year: {s.year_level}")
        
        print(f"\nCS Prof Elect 1 subjects found: {len(cs_prof_elect_1)}")
        for s in cs_prof_elect_1:
            print(f"  ID: {s.id}, Code: {s.code}, Type: {s.type}, Year: {s.year_level}")
        
        # Find schedules for these subjects
        all_subject_ids = [s.id for s in cc101 + cs_prof_elect_1]
        if all_subject_ids:
            related_schedules = db.query(models.Schedule).filter(
                models.Schedule.subject_id.in_(all_subject_ids)
            ).all()
            
            print(f"\nSchedules for CC 101 and CS Prof Elect 1:")
            for s in related_schedules:
                subject_code = subjects.get(s.subject_id, "Unknown")
                room_name = rooms.get(s.room_id, "Unknown")
                day_label = days.get(s.day_id, "Unknown")
                print(f"  ID {s.id}: {subject_code} | Room: {room_name} | Day: {day_label} | "
                      f"Time: {s.time} | Block: {s.block} | Year: {s.year}")
        
        return conflicts
        
    finally:
        db.close()

if __name__ == "__main__":
    check_room_conflicts()
