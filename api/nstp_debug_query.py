"""Quick DB query for NSTP debugging"""
from sqlalchemy import create_engine, text

engine = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/Scheduler_DB")
with engine.connect() as conn:
    r = conn.execute(text("SELECT id, course_id, instructor_id, day_id, semester FROM schedules WHERE id = 12171")).fetchone()
    if r:
        print(f"Schedule 12171: course_id={r[1]}, instructor_id={r[2]}, day_id={r[3]}, semester={r[4]}")
    else:
        print("Schedule 12171: Not found")
    
    rows = conn.execute(text("SELECT id, name, assignable_courses FROM instructors WHERE UPPER(assignable_courses) LIKE '%NSTP%' AND is_active = true")).fetchall()
    print(f"\nActive NSTP instructors ({len(rows)}):")
    for row in rows:
        print(f"  ID {row[0]}: {row[1]} -> {row[2]}")
