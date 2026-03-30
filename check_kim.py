import sys
import os
sys.path.append(os.getcwd())
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api import models

# Setup DB
db_path = "postgresql+psycopg2://postgres:ara@localhost:5432/Scheduler_DB"
engine = create_engine(db_path)
Session = sessionmaker(bind=engine)
db = Session()

def check_kim():
    instr = db.query(models.Instructor).get(14)
    if not instr:
        print("Instructor 14 not found")
        return
        
    print(f"Instructor: {instr.first_name} {instr.last_name} (ID: {instr.id})")
    print(f"Assignable Courses: {instr.assignable_courses}")
    
    if "NSTP" in (instr.assignable_courses or "").upper():
        print("VERDICT: QUALIFIED (Has NSTP)")
    else:
        print("VERDICT: NOT QUALIFIED (No NSTP)")

if __name__ == "__main__":
    check_kim()
