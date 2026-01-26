from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from api.models import Schedule, Timeslot
from api.db import DATABASE_URL

def debug_times():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- RAW SAMPLES FROM schedules TABLE ---")
    schedules = session.query(Schedule).limit(5).all()
    for s in schedules:
        print(f"Schedule ID {s.id}: time='{s.time}' (Raw String)")

    print("\n--- TIMESLOT DEFINITIONS ---")
    timeslots = session.query(Timeslot).order_by(Timeslot.start_min).limit(5).all()
    for t in timeslots:
        print(f"Timeslot ID {t.id}: start_min={t.start_min}, end_min={t.end_min}, label='{t.label}'")

    session.close()

if __name__ == "__main__":
    debug_times()
