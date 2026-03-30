import sys
sys.path.insert(0, '.')
from api.db import SessionLocal
from api.models import Room, Subject, Course, Schedule, Timeslot
from api.db_procedures import get_room_eligibility
from sqlalchemy import text

def parse_time_str_to_minutes(time_str):
    # e.g., '8:30 AM - 10:00 AM'
    def parse_one(t_str):
        t_str = t_str.strip()
        parts = t_str.split(' ')
        if len(parts) != 2: return 0
        time_part, period = parts
        h, m = map(int, time_part.split(':'))
        if period == 'PM' and h != 12: h += 12
        if period == 'AM' and h == 12: h = 0
        return h * 60 + m

    if '-' not in time_str: return 0, 0
    s_str, e_str = time_str.split('-')
    return parse_one(s_str), parse_one(e_str)

def analyze_true_capacity():
    session = SessionLocal()
    print("--- Detailed Timeslot Capacity Analysis ---")
    
    eligible_rooms_gen = get_room_eligibility(session, 66)
    eligible_rooms_lab = get_room_eligibility(session, 69)
    
    # Let's say workable hours are 7AM to 7PM = 12 hours = 24 slots per day. 5 days = 120 slots/week max.
    
    def analyze_room_set(name, rooms):
        print(f"\n--- {name} ---")
        total_rooms = len(rooms)
        print(f"Total Rooms: {total_rooms}")
        
        total_occupied_slots = 0
        for r in rooms:
            schedules = session.query(Schedule).filter(Schedule.room_id == r.id).all()
            room_slots_occupied = 0
            for s in schedules:
                try:
                    s_min, e_min = parse_time_str_to_minutes(s.time)
                    if e_min > s_min:
                        # each 30 mins is 1 slot
                        slots = (e_min - s_min) // 30
                        room_slots_occupied += slots
                        total_occupied_slots += slots
                except Exception:
                    pass
            print(f"Room {r.name}: Occupied {room_slots_occupied} slots (approx {(room_slots_occupied/120)*100:.1f}% of Mon-Fri 7am-7pm capacity)")
            
        max_possible = total_rooms * 120
        print(f"TOTAL SET OCCUPANCY: {total_occupied_slots} / {max_possible} slots ({(total_occupied_slots/max_possible)*100:.1f}%)")

    analyze_room_set("General Rooms (Used for OS 101)", eligible_rooms_gen)
    analyze_room_set("Computer Labs (Used for SE 2 and CS Elect 3)", eligible_rooms_lab)
    session.close()

if __name__ == "__main__":
    analyze_true_capacity()
