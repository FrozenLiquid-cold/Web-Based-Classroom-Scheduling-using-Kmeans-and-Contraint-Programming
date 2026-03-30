#!/usr/bin/env python3
"""
Test the fix for the PE 12 scheduling issue by running the scheduler directly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.scheduler.cp_scheduler import schedule_with_constraints_cp
from api import db
from sqlalchemy.orm import Session

def test_pe12_fix():
    """Test that PE 12 (ID: 18) can now access shared rooms"""
    
    # Create database session
    session = Session(db.engine)
    
    try:
        # Test parameters for the problematic case
        course_id = 4  # College 4
        year = 1
        semester = 1
        blocks_count = 2
        
        print(f"Testing PE 12 scheduling with:")
        print(f"  Course ID: {course_id}")
        print(f"  Year: {year}")
        print(f"  Semester: {semester}")
        print(f"  Blocks: {blocks_count}")
        
        # Run the scheduler
        result = schedule_with_constraints_cp(
            db=session,
            course_id=course_id,
            year=year,
            semester=semester,
            blocks_count=blocks_count,
            subject_ids=None,
            college_id=4
        )
        
        print(f"\nScheduler completed!")
        print(f"Success: {result.get('success', False)}")
        print(f"Total scheduled: {len(result.get('schedule', []))}")
        
        # Check if PE 12 was scheduled
        schedule = result.get('schedule', [])
        pe12_items = [item for item in schedule if item.get('subject_id') == 18]
        
        print(f"\nPE 12 (ID: 18) scheduled items: {len(pe12_items)}")
        for item in pe12_items:
            print(f"  - Block {item.get('block')}: {item.get('time')} in {item.get('room_name', 'Room ' + str(item.get('room_id')))}")
        
        if len(pe12_items) > 0:
            print("\n✓ SUCCESS: PE 12 was scheduled! The fix works.")
        else:
            print("\n✗ ISSUE: PE 12 was still not scheduled.")
            
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_pe12_fix()
