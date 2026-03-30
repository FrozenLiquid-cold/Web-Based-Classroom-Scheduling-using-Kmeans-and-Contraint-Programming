"""Debug: compare subject codes vs instructor assignable_courses"""
import re
from api.db import engine

conn = engine.raw_connection()
cur = conn.cursor()

cur.execute("SELECT id, code FROM subjects ORDER BY code")
subjects = cur.fetchall()
print("=== Subject Codes ===")
for s in subjects:
    print(f"  ID {s[0]}: {repr(s[1])}")

print()

cur.execute("SELECT id, first_name, last_name, assignable_courses FROM instructors WHERE is_active = true ORDER BY id")
instructors = cur.fetchall()

def normalize(s):
    return re.sub(r'[^A-Z0-9]', '', s.upper())

target_codes = ['SE 2', 'CS Elect 3-PD 101', 'CS Prof Elect 10', 'HCI 101', 'OS 101', 'THS 101', 'CS Prof Elect 9']
print("=== Matching Check ===")
for code in target_codes:
    norm_code = normalize(code)
    matches = []
    for instr in instructors:
        assignable = instr[3] or ''
        parts = [normalize(c) for c in assignable.split(',')]
        if norm_code in parts:
            matches.append(f"{instr[1]} {instr[2]} (ID {instr[0]})")
    status = f"{len(matches)} match(es)" if matches else "NO MATCH"
    print(f"\n  {code} (normalized: {norm_code}) => {status}")
    for m in matches:
        print(f"    - {m}")

print("\n=== Instructors with 'SE' in assignable_courses ===")
for instr in instructors:
    assignable = instr[3] or ''
    parts = [p.strip() for p in assignable.split(',')]
    se_parts = [p for p in parts if 'SE' in p.upper()]
    if se_parts:
        print(f"  ID {instr[0]} ({instr[1]} {instr[2]}): {se_parts}")

cur.close()
conn.close()
