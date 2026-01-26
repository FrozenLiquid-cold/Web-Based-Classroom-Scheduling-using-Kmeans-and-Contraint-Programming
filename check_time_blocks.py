import sys
import os
sys.path.append(os.getcwd())

from api.db import get_db
from sqlalchemy import text

def check_time_blocks():
    db = next(get_db())
    try:
        # Query all time_blocks
        stmt = text("""
            SELECT block_id, day_id, label, start_min, end_min, is_lab,
                   (end_min - start_min) as duration_min
            FROM time_blocks
            ORDER BY day_id, start_min
            LIMIT 50
        """)
        result = db.execute(stmt).fetchall()
        
        print(f"Found {len(result)} time_blocks:")
        print(f"{'ID':<5} {'Day':<5} {'Label':<20} {'Start':<6} {'End':<6} {'Dur':<5} {'IsLab':<6}")
        print("-" * 70)
        
        for row in result:
            print(f"{row.block_id:<5} {row.day_id:<5} {row.label:<20} {row.start_min:<6} {row.end_min:<6} {row.duration_min:<5} {row.is_lab}")
            
        # Count LAB slots
        lab_count = sum(1 for r in result if r.is_lab)
        print(f"\nLAB slots: {lab_count} out of {len(result)}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_time_blocks()
