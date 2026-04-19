"""Run migration 021: Add day_patterns table."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "scheduler.db")
SQL_PATH = os.path.join(os.path.dirname(__file__), "021_add_day_patterns.sql")

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    with open(SQL_PATH, "r") as f:
        sql = f.read()
    
    # Execute each statement separately
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                cursor.execute(stmt)
                print(f"OK: {stmt[:60]}...")
            except Exception as e:
                print(f"SKIP: {e}")
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT * FROM day_patterns ORDER BY priority")
    rows = cursor.fetchall()
    print(f"\nday_patterns table has {len(rows)} rows:")
    for row in rows:
        print(f"  {row}")
    
    conn.close()

if __name__ == "__main__":
    main()
