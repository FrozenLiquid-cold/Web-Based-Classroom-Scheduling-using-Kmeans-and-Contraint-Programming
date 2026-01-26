from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from api.models import Schedule, Timeslot
from api.db import DATABASE_URL

def debug_specific_times():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("\n--- CHECKING FOR 0-START TIMES (12:00 AM) ---")
    # Look for times clearly starting with 0- or 0–
    zero_start_schedules = session.query(Schedule).filter(
        (Schedule.time.like('0-%')) | (Schedule.time.like('0–%'))
    ).limit(5).all()

    if not zero_start_schedules:
        print("No schedules found starting with '0-'")
    else:
        for s in zero_start_schedules:
            print(f"FOUND 12:00 AM RECORD: Schedule ID {s.id}: time='{s.time}', Course: {s.course_id}, Room: {s.room_id}")

    print("\n--- CHECKING TIMESLOTS WITH START_MIN ~ 0 ---")
    # Check for timeslots that might start at midnight
    midnight_slots = session.query(Timeslot).filter(Timeslot.start_min == 0).all()
    if midnight_slots:
        for t in midnight_slots:
            print(f"MIDNIGHT TIMESLOT: ID {t.id}, label='{t.label}', start_min={t.start_min}")
    else:
        print("No Timeslots found with start_min == 0")

    print("\n--- CHECKING TIMESLOTS WITH START_MIN < 0 (Corrupted?) ---")
    neg_slots = session.query(Timeslot).filter(Timeslot.start_min < 0).limit(5).all()
    for t in neg_slots:
        print(f"CORRUPTED TIMESLOT: ID {t.id}, label='{t.label}', start_min={t.start_min}")

    session.close()

if __name__ == "__main__":
    debug_specific_times()
