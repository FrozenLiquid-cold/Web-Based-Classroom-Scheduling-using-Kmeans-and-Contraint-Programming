"""Check stored procedure definition"""
from api.db import engine

conn = engine.raw_connection()
cur = conn.cursor()
cur.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'get_instructor_eligibility'")
rows = cur.fetchall()
if rows:
    print(rows[0][0])
else:
    print("STORED PROCEDURE NOT FOUND")
cur.close()
conn.close()
