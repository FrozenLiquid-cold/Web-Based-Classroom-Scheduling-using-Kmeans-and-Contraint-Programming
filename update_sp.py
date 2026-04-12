"""Update stored procedure to enforce strict specialization"""
from api.db import engine

conn = engine.raw_connection()
cur = conn.cursor()

cur.execute("""
CREATE OR REPLACE FUNCTION public.get_instructor_eligibility(p_subject_id integer)
 RETURNS TABLE(instructor_id integer, first_name text, last_name text, college_id integer, assignable_courses text)
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_subject_code TEXT;
    v_norm_code TEXT;
BEGIN
    -- Get subject code
    SELECT s.code
    INTO v_subject_code
    FROM subjects s
    WHERE s.id = p_subject_id;

    -- Normalize: strip non-alphanum, then collapse Prof.E/ProE variants
    v_norm_code := UPPER(REGEXP_REPLACE(TRIM(v_subject_code), '[^A-Za-z0-9]', '', 'g'));
    v_norm_code := REGEXP_REPLACE(v_norm_code, 'PROFE(?=[0-9])', 'PROE', 'g');
    v_norm_code := REPLACE(v_norm_code, 'CSPROFELECT', 'CSPROE');

    RETURN QUERY
    SELECT
        i.id AS instructor_id,
        i.first_name::TEXT,
        i.last_name::TEXT,
        i.college_id,
        i.assignable_courses::TEXT
    FROM instructors i
    WHERE
        -- Only active instructors
        i.is_active = true
        AND
        -- Strict match with normalization (handles Prof.E vs ProE variants)
        i.assignable_courses IS NOT NULL
        AND v_subject_code IS NOT NULL
        AND v_norm_code = ANY(
            SELECT REPLACE(
                REGEXP_REPLACE(
                    UPPER(REGEXP_REPLACE(TRIM(unnest(string_to_array(i.assignable_courses, ','))), '[^A-Za-z0-9]', '', 'g')),
                    'PROFE(?=[0-9])', 'PROE', 'g'
                ),
                'CSPROFELECT', 'CSPROE'
            )
        )
    ORDER BY i.id;
END;
$function$
""")

conn.commit()
print("Stored procedure updated successfully!")

# Verify: test with a known subject
cur.execute("SELECT * FROM get_instructor_eligibility(69)")  # SE 2
rows = cur.fetchall()
print(f"\nSE 2 (ID 69) eligible instructors: {len(rows)}")
for r in rows:
    print(f"  ID {r[0]}: {r[1]} {r[2]} => {r[4][:60] if r[4] else 'None'}")

cur.execute("SELECT * FROM get_instructor_eligibility(66)")  # OS 101
rows = cur.fetchall()
print(f"\nOS 101 (ID 66) eligible instructors: {len(rows)}")
for r in rows:
    print(f"  ID {r[0]}: {r[1]} {r[2]} => {r[4][:60] if r[4] else 'None'}")

cur.close()
conn.close()
