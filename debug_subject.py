from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models import Schedule, Subject
from api.db import DATABASE_URL

def debug_subject_time():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- SEARCHING FOR IT 102 ---")
    results = session.query(Schedule).join(Subject).filter(Subject.code == 'IT 102').all()
    
    if not results:
        print("No schedules found for IT 102")
    
    for s in results:
        print(f"Schedule ID {s.id}: time='{s.time}'")
        
    print("\n--- SEARCHING FOR CC 102 ---")
    results = session.query(Schedule).join(Subject).filter(Subject.code == 'CC 102').all()
    for s in results:
        print(f"Schedule ID {s.id}: time='{s.time}'")

    session.close()

if __name__ == "__main__":
    debug_subject_time()
