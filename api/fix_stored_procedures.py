"""
Fix stored procedures by updating them with proper type casting.

This script updates all stored procedures to cast VARCHAR columns to TEXT
to match the function return types.
"""
import os
from db import SessionLocal
from sqlalchemy import text

def fix_stored_procedures():
    """Update all stored procedures with proper type casting."""
    db = SessionLocal()
    try:
        # Read the migration file
        migration_path = os.path.join(os.path.dirname(__file__), "migrations", "001_add_indexes_and_procedures.sql")
        
        if not os.path.exists(migration_path):
            print(f"[ERROR] Migration file not found: {migration_path}")
            return
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Extract only the stored procedure definitions (CREATE OR REPLACE FUNCTION)
        import re
        
        # Find all CREATE OR REPLACE FUNCTION blocks
        function_pattern = r'CREATE OR REPLACE FUNCTION.*?END;\s*\$\$ LANGUAGE plpgsql;'
        functions = re.findall(function_pattern, migration_sql, re.DOTALL)
        
        print(f"Found {len(functions)} stored procedures to update")
        
        # Execute each function
        success_count = 0
        for i, func_sql in enumerate(functions, 1):
            try:
                # Add semicolon if not present
                if not func_sql.strip().endswith(';'):
                    func_sql += ';'
                
                db.execute(text(func_sql))
                db.commit()
                success_count += 1
                print(f"[{i}/{len(functions)}] Updated stored procedure")
            except Exception as e:
                db.rollback()
                print(f"[{i}/{len(functions)}] Error: {e}")
                # Extract function name for better error message
                func_name_match = re.search(r'FUNCTION\s+(\w+)', func_sql)
                if func_name_match:
                    print(f"  Function: {func_name_match.group(1)}")
        
        print(f"\n[OK] Updated {success_count}/{len(functions)} stored procedures")
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error fixing stored procedures: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("Fixing stored procedures with proper type casting...")
    fix_stored_procedures()
    print("\n[OK] Done!")

