"""
Migration 018: Update time_blocks to the new clean 7:30 AM grid.

Replaces the old 19-block grid (with overlapping 7:00/7:30/8:00/8:30 starts)
with a clean 14-block grid starting at 7:30 AM.

Run from the api/ directory:
    python migrations/018_update_time_blocks.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import engine
from sqlalchemy import text

# New clean time grid: (block_id_offset, start_time, end_time, start_min, end_min, is_lab)
NEW_TIME_BLOCKS = [
    # Morning 1-hour slots
    (1,  "07:30", "08:30", 450,  510,  False),
    (2,  "09:00", "10:00", 540,  600,  False),
    (3,  "10:30", "11:30", 630,  690,  False),
    # Morning 1.5-hour slots
    (4,  "07:30", "09:00", 450,  540,  True),
    (5,  "09:00", "10:30", 540,  630,  True),
    (6,  "10:30", "12:00", 630,  720,  True),
    # Afternoon 1-hour slots
    (7,  "13:00", "14:00", 780,  840,  False),
    (8,  "14:30", "15:30", 870,  930,  False),
    (9,  "16:00", "17:00", 960,  1020, False),
    # Afternoon 1.5-hour slots
    (10, "13:00", "14:30", 780,  870,  True),
    (11, "14:30", "16:00", 870,  960,  True),
    (12, "16:00", "17:30", 960,  1050, True),
    # Evening
    (13, "17:30", "19:00", 1050, 1140, False),
    # NSTP (Sunday 3-hour block)
    (14, "08:00", "11:00", 480,  660,  False),
]


def run_migration():
    with engine.connect() as conn:
        # Count existing
        result = conn.execute(text("SELECT COUNT(*) FROM time_blocks"))
        old_count = result.scalar()
        print(f"Found {old_count} existing time block records")

        # Get all days
        result = conn.execute(text("SELECT id, label FROM days ORDER BY id"))
        days = result.fetchall()
        if not days:
            print("[ERROR] No days found in database. Cannot create time blocks.")
            return False

        print(f"Found {len(days)} days: {[d[1] for d in days]}")

        # Delete all existing time blocks
        conn.execute(text("DELETE FROM time_blocks"))
        print(f"Deleted {old_count} old time block records")

        # Insert new time blocks — one row per (block, day) combination
        inserted = 0
        block_counter = 0
        for day_id, day_label in days:
            for offset, start_str, end_str, start_min, end_min, is_lab in NEW_TIME_BLOCKS:
                block_counter += 1
                label = f"{start_str}–{end_str}"

                conn.execute(text("""
                    INSERT INTO time_blocks (block_id, day_id, label, start_time, end_time, start_min, end_min, is_lab)
                    VALUES (:block_id, :day_id, :label, :start_time, :end_time, :start_min, :end_min, :is_lab)
                """), {
                    "block_id": block_counter,
                    "day_id": day_id,
                    "label": label,
                    "start_time": start_str,
                    "end_time": end_str,
                    "start_min": start_min,
                    "end_min": end_min,
                    "is_lab": is_lab,
                })
                inserted += 1

        conn.commit()
        print(f"\n[OK] Inserted {inserted} new time block records ({len(NEW_TIME_BLOCKS)} blocks × {len(days)} days)")
        print("\nNew time grid (all days start at 7:30 AM):")
        print("  MORNING:   7:30-8:30, 9:00-10:00, 10:30-11:30 (1hr)")
        print("             7:30-9:00, 9:00-10:30, 10:30-12:00 (1.5hr)")
        print("  AFTERNOON: 1:00-2:00, 2:30-3:30, 4:00-5:00 (1hr)")
        print("             1:00-2:30, 2:30-4:00, 4:00-5:30 (1.5hr)")
        print("  EVENING:   5:30-7:00")
        print("  NSTP:      8:00-11:00 (Sunday)")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("Migration 018: Update Time Blocks to 7:30 AM Grid")
    print("=" * 60)
    success = run_migration()
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")
    sys.exit(0 if success else 1)
