import sys
sys.path.insert(0, '.')
from api.db import SessionLocal
from api.models import Room, Subject, Course, Instructor, Schedule
from api.db_procedures import get_room_eligibility
from sqlalchemy import text

def analyze_failures():
    session = SessionLocal()
    
    print("--- Room Capacity Analysis ---")
    
    # BSCS is course_id 4
    course_id = 4
    year = 4
    
    failed_ids = [65, 66, 69]
    
    # Get subjects
    subjects = session.query(Subject).filter(
        Subject.id.in_(failed_ids)
    ).all()
    
    print(f"Found {len(subjects)} matching subjects")
    
    for subj in subjects:
        print(f"\nSubject: {subj.code} ({subj.type}) ID: {subj.id}")
        eligible_rooms = get_room_eligibility(session, subj.id)
        room_ids = [r.id for r in eligible_rooms]
        print(f"  Eligible Rooms ({len(room_ids)}): {[r.name for r in eligible_rooms]}")
        
        # See what else is taking these rooms
        for room_id in room_ids:
            room_schedules = session.query(Schedule).filter(
                Schedule.room_id == room_id
            ).all()
            
            print(f"  - Room {room_id} has {len(room_schedules)} total bookings")
            
            # Print a few bookings
            if room_schedules:
                print(f"    Sample: {room_schedules[0].time} Day: {room_schedules[0].day_id} Course: {room_schedules[0].course_id}")
                
    session.close()

if __name__ == "__main__":
    analyze_failures()
