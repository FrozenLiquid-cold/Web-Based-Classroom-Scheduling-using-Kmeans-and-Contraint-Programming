import sys
import logging
sys.path.insert(0, '.')
from api.db import SessionLocal
from api.scheduler.cp_scheduler import run_cp_scheduler

def trace():
    session = SessionLocal()
    course_id = 4
    semester = 1
    blocks_count = 3
    # IDs from user's focus list
    focus = [72, 64, 65, 66, 67, 68, 69, 74, 71, 70, 73]
    
    print(f"Running scheduler trace for OS 101 (ID 66) and SE 2 (ID 68, 69)")
    
    # We will just run it but intercept the logs
    logger = logging.getLogger('api.scheduler.cp_scheduler')
    logger.setLevel(logging.DEBUG)
    
    # Write logs to a file to avoid stderr redirect issues
    fh = logging.FileHandler('trace_debug.log', mode='w')
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Let's see what gets returned from DB natively
    from api.db_procedures import get_subjects_for_scheduling
    subs = get_subjects_for_scheduling(session, course_id=4)
    filtered = [s for s in subs if getattr(s, 'id', None) in focus or str(getattr(s, 'id', None)) in map(str, focus)]
    print(f"Native Filtered Subjects: {[s.code for s in filtered]}")
    for s in filtered:
        print(f" - {s.code} (ID: {s.id}): Year={getattr(s, 'year_level', 'N/A')} ({type(getattr(s, 'year_level', None))}), Sem={getattr(s, 'semester', 'N/A')}")

    try:
        results, diags = run_cp_scheduler(
            db=session,
            course_id=course_id,
            year=4,
            semester=semester,
            block_count=blocks_count,
            years=[4],
            max_time_seconds=2,
            focus_subject_ids=focus,
        )
        os101_sched = [r for r in results if str(r.get('original_subject_id', '')) == '66' or str(r.get('subject_id', '')) == '66']
        print(f"\nScheduled OS 101 blocks: {len(os101_sched)}")
        for r in os101_sched:
            print(f" - Block {r.get('block')}: {r.get('room_name')} by {r.get('instructor_name')} on {r.get('day')} {r.get('time')}")
            
        print(f"\nAll keys in diags: {list(diags.keys())}")
        _raw = diags.get('_raw', {})
        unsched = diags.get('unscheduled_reasons', {})
        print(f"Final Diagnostics for 66 (OS 101): Raw={_raw.get('66')}, Unsched={unsched.get('66')}")
        print(f"Final Diagnostics for 69 (SE 2 LAB): Raw={_raw.get('69')}, Unsched={unsched.get('69')}")
    except Exception as e:
        print(f"Error: {e}")
        
    session.close()

if __name__ == "__main__":
    trace()
