"""Check for specific schedule conflict on Tuesday 9:00-10:30 in Comp Lab 1"""
from sqlalchemy import create_engine, text
from api.db import DATABASE_URL

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print('=== DETAILED: Room Double-Booking on Tuesday 9:00-10:30 ===')
    print()
    
    # Get all schedules in Comp Lab 1 on Tuesday 9:00-10:30
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
        s.semester,
        c.code as course_code
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE d.label = 'T'
    AND s.time LIKE '%9:00%10:30%'
    AND r.name = 'Comp Lab 1'
    ORDER BY s.id
    """
    result = conn.execute(text(query))
    rows = result.fetchall()
    
    print('*** Comp Lab 1 Conflicts ***')
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Course: {row[11]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
    
    # Get all schedules in Comp Lab 2 on Tuesday 9:00-10:30
    query2 = """
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
        s.semester,
        c.code as course_code
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE d.label = 'T'
    AND s.time LIKE '%9:00%10:30%'
    AND r.name = 'Comp Lab 2'
    ORDER BY s.id
    """
    result = conn.execute(text(query2))
    rows = result.fetchall()
    
    print('*** Comp Lab 2 Conflicts ***')
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Course: {row[11]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
    
    # Check specifically for CC 101 and CS Prof Elect 1 with Juan Dela Cruz and Feliz Dad
    print('=== CC 101 (Introduction to Computing) ===')
    cc101_query = """
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
        s.semester,
        c.code as course_code
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE subj.code = 'CC 101'
    AND d.label = 'T'
    AND s.time LIKE '%9:00%10:30%'
    ORDER BY s.id
    """
    result = conn.execute(text(cc101_query))
    rows = result.fetchall()
    
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Course: {row[11]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
    
    print('=== CS Prof Elect 1 (Digital Design) ===')
    csprof_query = """
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
        s.semester,
        c.code as course_code
    FROM schedules s
    LEFT JOIN days d ON s.day_id = d.id
    LEFT JOIN subjects subj ON s.subject_id = subj.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    LEFT JOIN rooms r ON s.room_id = r.id
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE subj.code = 'CS Prof Elect 1'
    AND d.label = 'T'
    AND s.time LIKE '%9:00%10:30%'
    ORDER BY s.id
    """
    result = conn.execute(text(csprof_query))
    rows = result.fetchall()
    
    for row in rows:
        print(f'  Schedule ID: {row[0]}')
        print(f'    Time: {row[1]}, Day: {row[2]}')
        print(f'    Subject: {row[3]} - {row[4]} ({row[5]})')
        print(f'    Instructor: {row[6]}')
        print(f'    Room: {row[7]}')
        print(f'    Course: {row[11]}')
        print(f'    Block: {row[8]}, Year: {row[9]}, Semester: {row[10]}')
        print()
