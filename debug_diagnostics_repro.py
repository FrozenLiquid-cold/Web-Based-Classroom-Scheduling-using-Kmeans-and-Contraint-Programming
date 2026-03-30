
import sys
import os
import logging

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db import SessionLocal

def get_session():
    return SessionLocal()
from api.scheduler.scheduler import run_scheduler
from api.models import Course

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_diagnostics():
    db = get_session()
    try:
        course_id = 3
        semester = 1 
        year = 2 
        block_count = 2
        
        print(f"\n--- Running Scheduler for Course {course_id}, Year {year}, Sem {semester} (Blocks: {block_count}) ---\n")
        
        # Load specific subject IDs if needed, otherwise run full year
        # focus_ids = [99, 93, 94, 96, 97, 98, 95, 90, 91, 92, 89]
        
        from api.scheduler.cp_scheduler import run_cp_scheduler
        
        # We need to construct the subjects list or pass IDs. 
        # run_scheduler usually does this looking up by course/year.
        # But let's try calling run_scheduler with the right params.
        
        results, diagnostics = run_scheduler(
            course_id=course_id,
            semester=semester,
            year=year,
            years=[year], # Just focus on this year
            block_capacity_overrides=None,
            db=db, 
            blocks_count=block_count 
        )
        
        print(f"\n--- Scheduler Finished ---")
        print(f"Scheduled Items: {len(results)}")
        print(f"Diagnostics Keys: {list(diagnostics.keys())}")
        
        # Check specific subjects
        print("\n--- Specifc Subject Check ---")
        focus_check_ids = [99, 199, 299, 96, 196, 296]
        found_count = 0
        for r in results:
            sid = r.get('subject_id')
            cid = r.get('clone_subject_id')
            if sid in focus_check_ids or cid in focus_check_ids:
                print(f"FOUND: Subject {sid} (Clone {cid}) Block {r.get('block')}")
                print(f"  - Time: {r.get('time')}")
                if r.get('time') is None or cid is None:
                    print(f"  - FULL ITEM: {r}")
                print(f"  - Room: {r.get('room_id')}")
                print(f"  - Day: {r.get('day_id')}")
                print(f"  - Start: {r.get('start_min')} End: {r.get('end_min')}")
                found_count += 1
        
        if found_count == 0:
            print("[!] SPECIFIC SUBJECTS NOT FOUND IN RESULTS!")

        if diagnostics:
            # Check for failure reasons
            reasons = [v.get('failure_reason') for v in diagnostics.values() if isinstance(v, dict) and v.get('failure_reason')]
            print(f"\n--- Failure Reasons Found: {len(reasons)} ---")
            for r in set(reasons):
                print(f" - {r}")
        else:
            print("\n[!] NO DIAGNOSTICS RETURNED!")

    except Exception as e:
        logger.exception("Test failed")
    finally:
        db.close()

if __name__ == "__main__":
    test_diagnostics()
