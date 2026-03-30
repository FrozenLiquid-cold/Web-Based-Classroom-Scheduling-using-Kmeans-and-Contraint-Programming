import logging
import sys
import os
sys.path.append(os.getcwd())
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api import models
from api.scheduler.cp_scheduler import time_to_minutes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup DB
db_path = "postgresql+psycopg2://postgres:ara@localhost:5432/Scheduler_DB"
print(f"Connecting to DB: {db_path}")

engine = create_engine(db_path)
Session = sessionmaker(bind=engine)
db = Session()

def debug_nstp():
    logger.info("DEBUG: Starting NSTP check...")
    
    # 1. Find NSTP Subject
    nstp_code = "NSTP 1" # or NSTP 2
    nstp_subjs = db.query(models.Subject).filter(models.Subject.code.ilike(f"%{nstp_code}%")).all()
    
    if not nstp_subjs:
        logger.error(f"Subject {nstp_code} not found!")
        # Try finding ANY
        all_subjs = db.query(models.Subject).limit(5).all()
        logger.info(f"Sample subjects: {[s.code for s in all_subjs]}")
        return
        
    nstp_subj = nstp_subjs[0]
    logger.info(f"Found NSTP Subject: {nstp_subj.code} (ID: {nstp_subj.id})")
    
    # 2. Find SUNDAY day
    sunday = db.query(models.Day).filter(models.Day.label.ilike("Sunday")).first()
    if not sunday:
        # Fallback to day 7?
        sunday = db.query(models.Day).filter(models.Day.id == 7).first()
    
    if not sunday:
         logger.error("Sunday day record NOT FOUND in DB!")
         days = db.query(models.Day).all()
         logger.info(f"Available days: {[d.label for d in days]}")
         return
         
    logger.info(f"Target Day: {sunday.label} (ID: {sunday.id})")
    
    # 3. Target Time
    start_min = 7 * 60
    end_min = 12 * 60
    logger.info(f"Target Time: {start_min}-{end_min} minutes (7:00 AM - 12:00 PM)")

    # 4. Check Instructors
    # Get eligible instructors
    eligible_instrs_rel = []
    try:
        from api.db_procedures import get_instructor_eligibility
        eligible_instrs_rel = get_instructor_eligibility(db, nstp_subj.id)
        eligible_instrs = [i for i in eligible_instrs_rel] if eligible_instrs_rel else []
        logger.info(f"SP Returned {len(eligible_instrs)} eligible intsructors.")
    except Exception as e:
        logger.warning(f"SP failed: {e}")
        eligible_instrs = []
        eligible_instrs_rel = []
        
    if not eligible_instrs:
        logger.warning("No eligible instructors found via SP. Falling back to all active.")
        eligible_instrs = db.query(models.Instructor).all() # Just check everyone
        
    logger.info(f"Checking {len(eligible_instrs)} instructors...")
    
    available_count = 0
    for instr in eligible_instrs:
        # Check conflict
        existing = db.query(models.Schedule).filter(
            models.Schedule.instructor_id == instr.id,
            models.Schedule.day_id == sunday.id
        ).all()
        
        status = "AVAILABLE"
        reason = ""
        
        if existing:
            status = "BUSY"
            reason = f"Has {len(existing)} other classes on Sunday: {[s.subject_id for s in existing]}"
            
        # Also check assignable_courses text
        assignable = (getattr(instr, "assignable_courses", "") or "").upper()
        
        # If we got results from SP, they are technically eligible by DB rules.
        # But let's check text too just to be sure.
        if "NSTP" not in assignable:
             if eligible_instrs_rel and instr in eligible_instrs_rel:
                 pass # SP said yes, trust SP? 
             else:
                 status = "INELIGIBLE"
                 text_reason = f"Does not have NSTP in assignable courses ({assignable})"
                 if status == "AVAILABLE": 
                      status = "INELIGIBLE"
                      reason = text_reason
                 else:
                      reason += f"; {text_reason}"

        logger.info(f"Instructor {instr.id} ({instr.first_name} {instr.last_name}): {status} {reason}")
        if status == "AVAILABLE":
            available_count += 1
            
    logger.info(f"Total Available Instructors for Sunday: {available_count}")

if __name__ == "__main__":
    debug_nstp()
