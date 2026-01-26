"""Run migration for swap_requests table"""
import sqlite3
import os

def run_migration():
    db_path = os.path.join(os.path.dirname(__file__), 'scheduler.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='swap_requests'")
    if cursor.fetchone():
        print("swap_requests table already exists")
        conn.close()
        return
    
    # Read and execute migration
    migration_path = os.path.join(os.path.dirname(__file__), 'migrations', '007_swap_requests.sql')
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    try:
        cursor.executescript(migration_sql)
        conn.commit()
        print("Successfully created swap_requests table")
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
