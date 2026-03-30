"""Debug: check which instructors the scheduler is using"""
from api.db import engine

conn = engine.raw_connection()
cur = conn.cursor()

# Get the instructors who appear in the schedule output
names = ['Andrew', 'John', 'Juan', 'Cathy', 'Feliz', 'Leo', 'Ella', 'Maria', 'Renz', 'Joaquin']
for name in names:
    cur.execute("SELECT id, first_name, last_name, assignable_courses FROM instructors WHERE first_name = %s", (name,))
    rows = cur.fetchall()
    for r in rows:
        print(f"ID {r[0]:3d} | {r[1]:12s} {r[2]:15s} | {(r[3] or '')[:80]}")

cur.close()
conn.close()
