"""Migration script to create a convenience view for reading schedules with joined names."""

from sqlalchemy import text

from .db import engine


def ensure_schedule_details_view():
    view_sql = """
    CREATE OR REPLACE VIEW schedule_details AS
    SELECT
        s.id AS schedule_id,
        s.course_id,
        c.code AS course_code,
        c.description AS course_description,
        s.subject_id,
        subj.code AS subject_code,
        subj.description AS subject_description,
        subj.type AS subject_type,
        subj.unit AS subject_unit,
        s.instructor_id,
        (COALESCE(i.first_name, '') || ' ' || COALESCE(i.middle_name, '') ||
         CASE WHEN i.middle_name IS NULL OR i.middle_name = '' THEN '' ELSE ' ' END ||
         COALESCE(i.last_name, '')) AS instructor_name,
        s.room_id,
        r.name AS room_name,
        r.type AS room_type,
        s.day_id,
        d.label AS day_label,
        s.time AS time_label,
        s.year,
        s.semester,
        s.block
    FROM schedules s
    LEFT JOIN courses c ON c.id = s.course_id
    LEFT JOIN subjects subj ON subj.id = s.subject_id
    LEFT JOIN instructors i ON i.id = s.instructor_id
    LEFT JOIN rooms r ON r.id = s.room_id
    LEFT JOIN days d ON d.id = s.day_id;
    """

    with engine.begin() as conn:
        conn.execute(text(view_sql))


if __name__ == "__main__":
    ensure_schedule_details_view()
