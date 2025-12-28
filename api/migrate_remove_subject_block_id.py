"""Remove block_id column from subjects table and update stored procedure"""
from sqlalchemy import inspect, text
from db import engine, SessionLocal
import os


def remove_block_id_column():
    """Remove block_id column from subjects table if it exists"""
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("subjects")}
    
    if "block_id" not in columns:
        print("[OK] subjects.block_id column does not exist (already removed)")
        return
    
    with engine.begin() as conn:
        print("[MIGRATION] Removing block_id column from subjects table...")
        try:
            conn.execute(text("ALTER TABLE subjects DROP COLUMN block_id"))
            print("[DONE] block_id column removed.")
        except Exception as e:
            print(f"[WARNING] Error removing column: {e}")
            print("  (This is OK if the column doesn't exist)")


def update_stored_procedure():
    """Update the stored procedure to remove block_id"""
    db = SessionLocal()
    try:
        migration_path = os.path.join(os.path.dirname(__file__), "migrations", "001_add_indexes_and_procedures.sql")
        
        if not os.path.exists(migration_path):
            print(f"[WARNING] Migration file not found: {migration_path}")
            return
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Find and execute just the get_subjects_for_scheduling function
        # Extract the function definition
        import re
        pattern = r'CREATE OR REPLACE FUNCTION get_subjects_for_scheduling.*?END;'
        match = re.search(pattern, migration_sql, re.DOTALL | re.IGNORECASE)
        
        if match:
            function_sql = match.group(0)
            print("[MIGRATION] Updating get_subjects_for_scheduling stored procedure...")
            db.execute(text(function_sql))
            db.commit()
            print("[DONE] Stored procedure updated.")
        else:
            print("[WARNING] Could not find get_subjects_for_scheduling function in migration file")
            
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error updating stored procedure: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("Removing block_id from subjects table...")
    remove_block_id_column()
    print("\nUpdating stored procedure...")
    update_stored_procedure()
    print("\n[OK] Migration complete!")


