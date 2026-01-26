"""
Migration script to fix corrupted time_blocks table.
This script:
1. Clears the existing time_blocks table
2. Repopulates it with correct data including:
   - Proper start_min/end_min values
   - day_id for each day (M, T, W, TH, F)
   - is_lab flag for LAB-appropriate slots
   - Human-readable labels
"""
import sys
import os
sys.path.append(os.getcwd())

from api.db import SessionLocal, engine
from api import models
from sqlalchemy import text

# Time blocks based on registrar windows (from timeslots.py)
TIME_BLOCKS = [
    {"label": "7:00–8:30", "start": "07:00", "end": "08:30", "is_lab": False},
    {"label": "7:30–8:30", "start": "07:30", "end": "08:30", "is_lab": False},
    {"label": "7:30–9:00 LAB", "start": "07:30", "end": "09:00", "is_lab": True},
    {"label": "8:00–9:00", "start": "08:00", "end": "09:00", "is_lab": False},
    {"label": "8:30–10:00", "start": "08:30", "end": "10:00", "is_lab": False},
    {"label": "9:00–10:00", "start": "09:00", "end": "10:00", "is_lab": False},
    {"label": "9:00–10:30 LAB", "start": "09:00", "end": "10:30", "is_lab": True},
    {"label": "9:00–12:00", "start": "09:00", "end": "12:00", "is_lab": False},
    {"label": "10:30–11:30", "start": "10:30", "end": "11:30", "is_lab": False},
    {"label": "10:30–12:00 LAB", "start": "10:30", "end": "12:00", "is_lab": True},
    {"label": "11:00–12:00", "start": "11:00", "end": "12:00", "is_lab": False},
    {"label": "13:00–14:00", "start": "13:00", "end": "14:00", "is_lab": False},
    {"label": "13:00–14:30", "start": "13:00", "end": "14:30", "is_lab": False},
    {"label": "13:00–15:00", "start": "13:00", "end": "15:00", "is_lab": False},
    {"label": "14:00–15:00", "start": "14:00", "end": "15:00", "is_lab": False},
    {"label": "14:30–16:00 LAB", "start": "14:30", "end": "16:00", "is_lab": True},
    {"label": "15:00–17:00", "start": "15:00", "end": "17:00", "is_lab": False},
    {"label": "16:00–17:30 LAB", "start": "16:00", "end": "17:30", "is_lab": True},
    {"label": "17:30–19:00", "start": "17:30", "end": "19:00", "is_lab": False},
]

DAY_IDS = {
    "M": 1,
    "T": 2,
    "W": 3,
    "TH": 4,
    "F": 5,
}

def time_to_minutes(time_str: str) -> int:
    """Convert HH:MM to minutes since midnight."""
    if not time_str:
        return 0
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def fix_time_blocks():
    db = SessionLocal()
    try:
        # First, verify days exist
        days = db.query(models.Day).all()
        if not days:
            print("[ERROR] No days found in database. Cannot proceed.")
            return False
        
        day_map = {d.label: d.id for d in days}
        print(f"Found days: {day_map}")
        
        # Count existing time_blocks
        existing_count = db.query(models.TimeBlock).count()
        print(f"Existing time_blocks: {existing_count}")
        
        # Clear existing time_blocks
        print("Clearing existing time_blocks...")
        db.execute(text("DELETE FROM time_blocks"))
        db.commit()
        print("  - Cleared.")
        
        # Insert new time_blocks for each day
        print("Inserting corrected time_blocks...")
        block_id = 1
        inserted = 0
        
        for day_label, day_id in sorted(DAY_IDS.items(), key=lambda x: x[1]):
            actual_day_id = day_map.get(day_label, day_id)
            
            for block in TIME_BLOCKS:
                start_min = time_to_minutes(block["start"])
                end_min = time_to_minutes(block["end"])
                label = f"{day_label} {block['label']}"
                
                # Create block_id: day_id * 100 + index
                unique_block_id = actual_day_id * 100 + (inserted % len(TIME_BLOCKS)) + 1
                
                time_block = models.TimeBlock(
                    block_id=unique_block_id,
                    day_id=actual_day_id,
                    label=label,
                    start_time=block["start"],
                    end_time=block["end"],
                    start_min=start_min,
                    end_min=end_min,
                    is_lab=block["is_lab"],
                )
                db.add(time_block)
                inserted += 1
                
                if inserted <= 5:
                    print(f"  - {label}: start_min={start_min}, end_min={end_min}, is_lab={block['is_lab']}")
        
        db.commit()
        print(f"\n[OK] Inserted {inserted} time_blocks ({len(TIME_BLOCKS)} blocks × {len(DAY_IDS)} days)")
        
        # Verify
        verify_count = db.query(models.TimeBlock).count()
        lab_count = db.query(models.TimeBlock).filter(models.TimeBlock.is_lab == True).count()
        print(f"[OK] Verification: {verify_count} total blocks, {lab_count} LAB blocks")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("TIME_BLOCKS MIGRATION SCRIPT")
    print("=" * 60)
    print()
    
    success = fix_time_blocks()
    
    if success:
        print("\n✓ Migration completed successfully!")
        print("  LAB subjects should now get 90-minute (1.5 hour) slots.")
    else:
        print("\n✗ Migration failed. Check errors above.")
