"""Check for schedule conflict on Tuesday 9:00-10:30"""
from sqlalchemy import create_engine, text
from api.db import DATABASE_URL

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Get the day ID for Tuesday (T)
    day_result = conn.execute(text("SELECT id, label FROM days WHERE label = 'T'"))
    day_rows = day_result.fetchall()
    print('=== Day T (Tuesday) ===')
    for row in day_rows:
        print(f'  Day ID: {row[0]}, Label: {row[1]}')
    
    # Find schedules with time 9:00-10:30 on Tuesday
    print()
    print('=== Schedules on T 9:00-10:30 (LAB) ===')
    query = """
    SELECT 
        s.id,
        s.time,
        d.label as day,
        subj.code as subject_code,
        subj.description as subject_desc,
        subj.type as subject_type,
        CONCAT(i.first_name, ' ', i.last_name) as instructor_name,
        r.name as room_name,
        s.block,
        s.year,
        s.semester
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    WHERE d.label = 'T'
    AND s.time LIKE '%9:00%10:30%'
    ORDER BY s.id
    """
    result = conn.execute(text(query))
    rows = result.fetchall()
    
    if not rows:
        print('  No schedules found for this time slot.')
    
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
    
    # Also search specifically for the subject codes
    print()
    print('=== Searching for CC 101 and CS Prof Elect 1 ===')
    subj_query = """
    SELECT 
        s.id,
        s.time,
        d.label as day,
        subj.code as subject_code,
        subj.description as subject_desc,
        subj.type as subject_type,
        CONCAT(i.first_name, ' ', i.last_name) as instructor_name,
        r.name as room_name,
        s.block,
        s.year,
        s.semester
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    WHERE subj.code IN ('CC 101', 'CS Prof Elect 1')
       OR subj.description ILIKE '%Introduction to Computing%'
       OR subj.description ILIKE '%Digital Design%'
    ORDER BY s.id
    """
    result = conn.execute(text(subj_query))
    rows = result.fetchall()
    
    if not rows:
        print('  No schedules found for these subjects.')
    
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
    
    # Search for instructors Juan Dela Cruz and Feliz Dad
    print()
    print('=== Searching for Instructors: Juan Dela Cruz & Feliz Dad ===')
    instr_query = """
    SELECT 
        s.id,
        s.time,
        d.label as day,
        subj.code as subject_code,
        subj.description as subject_desc,
        subj.type as subject_type,
        CONCAT(i.first_name, ' ', i.last_name) as instructor_name,
        r.name as room_name,
        s.block,
        s.year,
        s.semester
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    WHERE (i.first_name ILIKE '%Juan%' AND i.last_name ILIKE '%Dela Cruz%')
       OR (i.first_name ILIKE '%Feliz%' AND i.last_name ILIKE '%Dad%')
    ORDER BY d.label, s.time
    """
    result = conn.execute(text(instr_query))
    rows = result.fetchall()
    
    if not rows:
        print('  No schedules found for these instructors.')
    
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
    
    # Check for any room double-booking on Tuesday 9:00-10:30
    print()
    print('=== Checking for Room Double-Booking on Tuesday 9:00-10:30 ===')
    room_query = """
    SELECT 
        r.name as room_name,
        COUNT(*) as schedule_count,
        STRING_AGG(subj.code || ' (' || CONCAT(i.first_name, ' ', i.last_name) || ')', ', ') as schedules
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    WHERE d.label = 'T'
    AND s.time LIKE '%9:00%10:30%'
    GROUP BY r.id, r.name
    HAVING COUNT(*) > 1
    ORDER BY r.name
    """
    result = conn.execute(text(room_query))
    rows = result.fetchall()
    
    if not rows:
        print('  No room double-bookings detected.')
    
    for row in rows:
        print(f'  CONFLICT FOUND: Room {row[0]} has {row[1]} schedules!')
        print(f'    Schedules: {row[2]}')
        print()
