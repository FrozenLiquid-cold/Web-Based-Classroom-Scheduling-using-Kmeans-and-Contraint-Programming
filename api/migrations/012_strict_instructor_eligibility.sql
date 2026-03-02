-- Migration: Enforce strict instructor specialization in eligibility SP
-- Only instructors with the subject code in assignable_courses are eligible
-- Also filters by is_active = true

CREATE OR REPLACE FUNCTION public.get_instructor_eligibility(p_subject_id integer)
 RETURNS TABLE(instructor_id integer, first_name text, last_name text, college_id integer, assignable_courses text)
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_subject_code TEXT;
BEGIN
    -- Get subject code
    SELECT s.code
    INTO v_subject_code
    FROM subjects s
    WHERE s.id = p_subject_id;
    
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
        -- Strict match: subject code must be in assignable_courses
        i.assignable_courses IS NOT NULL 
        AND v_subject_code IS NOT NULL
        AND UPPER(REGEXP_REPLACE(TRIM(v_subject_code), '[^A-Z0-9]', '', 'g')) = ANY(
            SELECT UPPER(REGEXP_REPLACE(TRIM(unnest(string_to_array(i.assignable_courses, ','))), '[^A-Z0-9]', '', 'g'))
        )
    ORDER BY i.id;
END;
$function$;
