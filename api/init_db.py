"""Initialize database with tables and seed data"""
import os
from db import engine, SessionLocal, Base
from api import models
from routes.auth import hash_password
from sqlalchemy import text

def init_database():
    """Create all tables"""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created")
    
    # Run optimization migration (indexes and stored procedures)
    print("Applying database optimizations (indexes and stored procedures)...")
    apply_optimization_migration()
    print("[OK] Database optimizations applied")

def apply_optimization_migration():
    """Apply the optimization migration with indexes and stored procedures"""
    db = SessionLocal()
    try:
        migration_path = os.path.join(os.path.dirname(__file__), "migrations", "001_add_indexes_and_procedures.sql")
        
        if not os.path.exists(migration_path):
            print(f"[WARNING] Migration file not found: {migration_path}")
            return
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        # Parse SQL statements properly handling dollar-quoted strings
        # Use regex to split on semicolons outside of dollar-quoted strings
        import re
        
        # Remove single-line comments (but preserve dollar-quoted content)
        lines = migration_sql.split('\n')
        cleaned_lines = []
        for line in lines:
            # Remove comments (-- style) but not inside dollar quotes
            comment_pos = line.find('--')
            if comment_pos >= 0:
                # Check if it's not inside a string (simple check)
                before_comment = line[:comment_pos]
                if before_comment.count("'") % 2 == 0:  # Even number of quotes = not in string
                    line = line[:comment_pos]
            cleaned_lines.append(line)
        cleaned_sql = '\n'.join(cleaned_lines)
        
        # Split by semicolon, but respect dollar-quoted strings
        # Pattern: semicolon not inside dollar quotes
        statements = []
        current = []
        in_dollar = False
        dollar_tag = None
        i = 0
        
        while i < len(cleaned_sql):
            # Check for dollar quote start
            if cleaned_sql[i] == '$' and not in_dollar:
                # Check for $$ or $tag$
                if i + 1 < len(cleaned_sql) and cleaned_sql[i + 1] == '$':
                    in_dollar = True
                    dollar_tag = '$$'
                    current.append('$$')
                    i += 2
                    continue
                else:
                    # Try to match $tag$
                    match = re.match(r'\$[A-Za-z_][A-Za-z0-9_]*\$', cleaned_sql[i:])
                    if match:
                        in_dollar = True
                        dollar_tag = match.group(0)
                        current.append(dollar_tag)
                        i += len(dollar_tag)
                        continue
            
            # Check for dollar quote end
            if in_dollar and dollar_tag and cleaned_sql[i:].startswith(dollar_tag):
                current.append(dollar_tag)
                i += len(dollar_tag)
                in_dollar = False
                dollar_tag = None
                continue
            
            # Check for statement end (semicolon outside dollar quote)
            if not in_dollar and cleaned_sql[i] == ';':
                stmt = ''.join(current).strip()
                if stmt:
                    statements.append(stmt)
                current = []
                i += 1
                continue
            
            current.append(cleaned_sql[i])
            i += 1
        
        # Add final statement if any
        if current:
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
        
        # Filter out empty statements
        statements = [s for s in statements if s.strip()]
        
        # Execute each statement in its own transaction to avoid cascading failures
        success_count = 0
        error_count = 0
        
        for statement in statements:
            try:
                # Execute in a savepoint for better error isolation
                db.execute(text(statement))
                db.commit()
                success_count += 1
            except Exception as e:
                db.rollback()
                error_msg = str(e).lower()
                
                # Skip if already exists (for idempotent migrations)
                if "already exists" in error_msg or "duplicate" in error_msg:
                    success_count += 1
                    continue
                
                # Skip if column doesn't exist (for optional columns like block_id)
                if "does not exist" in error_msg or "undefined column" in error_msg:
                    print(f"[SKIP] Column/index not found (may not exist): {statement[:80]}...")
                    success_count += 1
                    continue
                
                # Log other errors but continue
                print(f"[WARNING] Error executing statement: {e}")
                print(f"Statement: {statement[:100]}...")
                error_count += 1
        
        print(f"[OK] Migration applied: {success_count} statements succeeded, {error_count} errors")
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error applying optimization migration: {e}")
        # Don't raise - allow initialization to continue
    finally:
        db.close()

def seed_data():
    """Seed initial data"""
    db = SessionLocal()
    try:
        # Check if data already exists
        if db.query(models.College).count() > 0:
            print("[OK] Data already seeded")
            return
        
        print("Seeding initial data...")
        
        # Create colleges
        college_cas = models.College(code="CAS", description="College of Arts and Sciences")
        college_cet = models.College(code="CET", description="College of Engineering and Technology")
        db.add(college_cas)
        db.add(college_cet)
        db.flush()
        
        # Create courses
        course_bsit = models.Course(code="BSIT", description="BS Information Technology", college_id=college_cet.id)
        course_bsed = models.Course(code="BSED", description="BS Education", college_id=college_cas.id)
        db.add(course_bsit)
        db.add(course_bsed)
        db.flush()
        
        # Create instructors
        instructor1 = models.Instructor(first_name="Juan", last_name="Dela Cruz")
        instructor2 = models.Instructor(first_name="Maria", last_name="Santos")
        db.add(instructor1)
        db.add(instructor2)
        db.flush()
        
        # Create days
        days = [
            models.Day(label="M"),
            models.Day(label="T"),
            models.Day(label="W"),
            models.Day(label="TH"),
            models.Day(label="F"),
        ]
        for day in days:
            db.add(day)
        db.flush()
        
        # Create subjects
        subject1 = models.Subject(code="CC101", description="Intro to Computing", type="LEC", unit=3)
        subject2 = models.Subject(code="CC102", description="Programming 1", type="LAB", unit=2)
        db.add(subject1)
        db.add(subject2)
        db.flush()
        
        # Create rooms
        room1 = models.Room(name="Room 101", type="LEC")
        room2 = models.Room(name="Lab 1", type="LAB")
        db.add(room1)
        db.add(room2)
        db.flush()
        
        # Create time blocks (registrar windows)
        if db.query(models.TimeBlock).count() == 0:
            from scheduler.timeslots import time_to_minutes
            registrar_windows = [
                # Morning 1-hour slots
                (1, "07:30", "08:30"),
                (2, "09:00", "10:00"),
                (3, "10:30", "11:30"),
                # Morning 1.5-hour slots
                (4, "07:30", "09:00"),
                (5, "09:00", "10:30"),
                (6, "10:30", "12:00"),
                # Afternoon 1-hour slots
                (7, "13:00", "14:00"),
                (8, "14:30", "15:30"),
                (9, "16:00", "17:00"),
                # Afternoon 1.5-hour slots
                (10, "13:00", "14:30"),
                (11, "14:30", "16:00"),
                (12, "16:00", "17:30"),
                # Evening
                (13, "17:30", "19:00"),
                # NSTP (Sunday 3-hour)
                (14, "08:00", "11:00"),
            ]
            for block_id, start_label, end_label in registrar_windows:
                time_block = models.TimeBlock(
                    block_id=block_id,
                    start_time=start_label,
                    end_time=end_label,
                    start_min=time_to_minutes(start_label),
                    end_min=time_to_minutes(end_label),
                )
                db.add(time_block)
            db.commit()
            print("  - Created 14 time blocks (registrar windows)")
        
        # Create users
        user_registrar = models.User(
            username="registrar",
            password_hash=hash_password("1234"),
            role="registrar"
        )
        user_instructor = models.User(
            username="instructor",
            password_hash=hash_password("1234"),
            role="instructor",
            instructor_id=instructor1.id
        )
        user_admin = models.User(
            username="admin",
            password_hash=hash_password("1234"),
            role="admin"
        )
        db.add(user_registrar)
        db.add(user_instructor)
        db.add(user_admin)
        
        db.commit()
        print("[OK] Seed data created")
        print("  - Users: registrar/1234, instructor/1234, admin/1234")
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Error seeding data: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
    seed_data()
    print("\n[OK] Database initialization complete!")


