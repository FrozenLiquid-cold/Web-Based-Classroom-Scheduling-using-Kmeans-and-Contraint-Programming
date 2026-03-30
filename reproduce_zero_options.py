
import sys
import os
import logging
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from api.scheduler.cp_scheduler import generate_subject_start_options, _find_matching_slot

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def run_test():
    print("=== Testing generate_subject_start_options ===")
    
    # Mock data
    class MockSubject:
        def __init__(self, id, code, type, hours_lec=0, hours_lab=0):
            self.id = id
            self.code = code
            self.type = type
            self.subject_type = type  # Simulate what might be happening with getattr fallback? 
                                      # Actually cp_scheduler tries getattr(s, 'subject_type', '?')
            self.hours_lec = hours_lec
            self.hours_lab = hours_lab

    # 1. Test Case: LEC subject with mismatched MW slots
    print("\n--- Test Case 1: LEC subject (MW pattern) with mismatched slots ---")
    subj_lec = MockSubject(1, "LEC101", "LEC", 3, 0)
    
    # Slots: Mon 7:30-9:00, Wed 8:00-9:30 (Mismatch)
    slots_mismatch = {
        "M": [{
            "day": "M", "index": 0, "label": "7:30-9:00", 
            "start_min": 450, "end_min": 540, 
            "block_indices": {0}, "blocks_spanned": {0}
        }],
        "W": [{
            "day": "W", "index": 0, "label": "8:00-9:30", 
            "start_min": 480, "end_min": 570,
            "block_indices": {0}, "blocks_spanned": {0}
        }],
        "T": [], "TH": [], "F": []
    }
    
    class MockDay:
        def __init__(self, id, label):
            self.id = id
            self.label = label
            
    days = [MockDay(1, "M"), MockDay(2, "T"), MockDay(3, "W"), MockDay(4, "TH"), MockDay(5, "F")]
    slot_to_block_map = {}
    
    options = generate_subject_start_options(
        subject=subj_lec,
        slots_by_day=slots_mismatch,
        slot_to_block_map=slot_to_block_map,
        days=days,
        logger=logger
    )
    print(f"Options generated: {len(options)}")
    if not options:
        print("  -> Expected result: No options due to mismatched MW slots.")

    # 2. Test Case: LAB subject with valid F slot
    print("\n--- Test Case 2: LAB subject with valid F slot ---")
    subj_lab = MockSubject(2, "LAB101", "LAB", 0, 3)
    
    slots_lab = {
        "M": [], "W": [], "T": [], "TH": [],
        "F": [{
            "day": "F", "index": 0, "label": "7:30-10:30", 
            "start_min": 450, "end_min": 630,
            "block_indices": {0, 1}, "blocks_spanned": {0, 1}
        }]
    }
    
    options = generate_subject_start_options(
        subject=subj_lab,
        slots_by_day=slots_lab,
        slot_to_block_map=slot_to_block_map,
        days=days,
        logger=logger
    )
    print(f"Options generated: {len(options)}")
    if options:
        print(f"  -> Success: Found {len(options)} options.")
        print(f"  -> Option: {options[0]}")

    # 3. Test Case: LEC subject with matching MW slots
    print("\n--- Test Case 3: LEC subject with matching MW slots ---")
    slots_match = {
        "M": [{
            "day": "M", "index": 0, "label": "7:30-9:00", 
            "start_min": 450, "end_min": 540, 
            "block_indices": {0}, "blocks_spanned": {0}
        }],
        "W": [{
            "day": "W", "index": 0, "label": "7:30-9:00", 
            "start_min": 450, "end_min": 540,
            "block_indices": {0}, "blocks_spanned": {0}
        }],
        "T": [], "TH": [], "F": []
    }
    
    options = generate_subject_start_options(
        subject=subj_lec,
        slots_by_day=slots_match,
        slot_to_block_map=slot_to_block_map,
        days=days,
        logger=logger
    )
    print(f"Options generated: {len(options)}")
    if options:
        print(f"  -> Success: Found {len(options)} options.")

if __name__ == "__main__":
    run_test()
