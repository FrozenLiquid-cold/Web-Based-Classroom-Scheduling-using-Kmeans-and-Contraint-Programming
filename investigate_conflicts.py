"""
Deep investigation of WHY room double-bookings happened
"""
import sys
from pathlib import Path

project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from api.db import SessionLocal
from api import models
from collections import defaultdict

def investigate_conflicts():
    db = SessionLocal()
    try:
        # Get all schedules
        schedules = db.query(models.Schedule).all()
        
        # Get room names
        rooms = {r.id: r.name for r in db.query(models.Room).all()}
        
        # Get day labels 
        days = {d.id: d.label for d in db.query(models.Day).all()}
        
        # Get subject info
        subjects = {s.id: {"code": s.code, "course_id": s.course_id, "year_level": s.year_level, "semester": s.semester} 
                   for s in db.query(models.Subject).all()}
        
        # Get course info
        courses = {c.id: c.description for c in db.query(models.Course).all()}
        
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
        
        print(f"TOTAL CONFLICTS: {len(conflicts)}")
        print()
        
        # Analyze patterns
        conflict_patterns = defaultdict(int)
        same_course_conflicts = []
        different_course_conflicts = []
        same_semester_conflicts = []
        different_semester_conflicts = []
        
        for conflict in conflicts:
            items = conflict['items']
            
            # Get course info for each item
            course_ids = set()
            semester_ids = set()
            year_levels = set()
            
            for item in items:
                subj_info = subjects.get(item.subject_id, {})
                course_ids.add(subj_info.get("course_id"))
                semester_ids.add(item.semester)
                year_levels.add(item.year)
            
            if len(course_ids) == 1:
                same_course_conflicts.append(conflict)
            else:
                different_course_conflicts.append(conflict)
            
            if len(semester_ids) == 1:
                same_semester_conflicts.append(conflict)
            else:
                different_semester_conflicts.append(conflict)
        
        print("=" * 80)
        print("CONFLICT ANALYSIS")
        print("=" * 80)
        print(f"Same course conflicts: {len(same_course_conflicts)}")
        print(f"Different course conflicts: {len(different_course_conflicts)}")
        print(f"Same semester conflicts: {len(same_semester_conflicts)}")  
        print(f"DIFFERENT semester conflicts: {len(different_semester_conflicts)}")
        print()
        
        # Show details of different semester conflicts
        if different_semester_conflicts:
            print("=" * 80)
            print("DIFFERENT SEMESTER CONFLICTS (root cause likely):")
            print("=" * 80)
            for i, conflict in enumerate(different_semester_conflicts[:10]):
                print(f"\n--- Conflict {i+1} ---")
                print(f"Room: {conflict['room_name']}, Day: {conflict['day_label']}, Time: {conflict['time']}")
                for item in conflict['items']:
                    subj_info = subjects.get(item.subject_id, {})
                    course_name = courses.get(subj_info.get("course_id"), "Unknown")
                    print(f"  - Subject: {subj_info.get('code')} | Course: {course_name} | "
                          f"Year: {item.year} | Semester: {item.semester} | Block: {item.block}")
        
        # Show sample of same semester conflicts to understand the pattern
        print()
        print("=" * 80)
        print("SAME SEMESTER CONFLICTS (sample):")
        print("=" * 80)
        for i, conflict in enumerate(same_semester_conflicts[:5]):
            print(f"\n--- Conflict {i+1} ---")
            print(f"Room: {conflict['room_name']}, Day: {conflict['day_label']}, Time: {conflict['time']}")
            for item in conflict['items']:
                subj_info = subjects.get(item.subject_id, {})
                course_name = courses.get(subj_info.get("course_id"), "Unknown")
                print(f"  - Subject: {subj_info.get('code')} | Course: {course_name} | "
                      f"Year: {item.year} | Semester: {item.semester} | Block: {item.block}")
        
        # Check if conflicts span multiple schedule.year values
        year_cross_conflicts = []
        for conflict in conflicts:
            items = conflict['items']
            years = set(item.year for item in items)
            if len(years) > 1:
                year_cross_conflicts.append(conflict)
        
        print()
        print("=" * 80)
        print(f"CONFLICTS ACROSS DIFFERENT YEAR LEVELS: {len(year_cross_conflicts)}")
        print("=" * 80)
        for i, conflict in enumerate(year_cross_conflicts[:5]):
            print(f"\n--- Conflict {i+1} ---")
            print(f"Room: {conflict['room_name']}, Day: {conflict['day_label']}, Time: {conflict['time']}")
            for item in conflict['items']:
                subj_info = subjects.get(item.subject_id, {})
                print(f"  - Subject: {subj_info.get('code')} | Year: {item.year} | Semester: {item.semester} | Block: {item.block}")
                
    finally:
        db.close()

if __name__ == "__main__":
    investigate_conflicts()
