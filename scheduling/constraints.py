from datetime import datetime

def parse_time_range(time_str):
    """Convert 'HH:MM' into minutes."""
    t = datetime.strptime(time_str.strip(), "%H:%M")
    return t.hour * 60 + t.minute

def overlap(start1, end1, start2, end2):
    """Return True if two ranges overlap."""
    return not (end1 <= start2 or end2 <= start1)

def is_valid_assignment(schedule, cand, g):
    """
    Validate a candidate against the current schedule.
    cand keys: 'Day', 'Start', 'End', 'Room', 'Instructor', 'Block', 'YearLevel', 'Semester'
    """
    cand_start = parse_time_range(cand["Start"])
    cand_end   = parse_time_range(cand["End"])
    cand_day   = cand["Day"]

    for assigned in schedule:
        assigned_start = parse_time_range(assigned["Start"])
        assigned_end   = parse_time_range(assigned["End"])
        assigned_day   = assigned["Day"]

        # Same day required for conflicts
        if assigned_day != cand_day:
            continue

        # Room conflict
        if assigned["Room"] == cand["Room"] and overlap(cand_start, cand_end, assigned_start, assigned_end):
            print(f"❌ Room conflict: {cand['Room']} on {cand_day} "
                  f"{cand['Start']}-{cand['End']} overlaps with "
                  f"{assigned['Code']} {assigned['Start']}-{assigned['End']}")
            return False

        # Instructor conflict
        if assigned["Instructor"] == cand["Instructor"] and overlap(cand_start, cand_end, assigned_start, assigned_end):
            print(f"❌ Instructor conflict: {cand['Instructor']} on {cand_day} "
                  f"{cand['Start']}-{cand['End']} overlaps with "
                  f"{assigned['Code']} {assigned['Start']}-{assigned['End']}")
            return False

        # Block/year conflict
        if (assigned["Block"] == g.block and
            assigned["YearLevel"] == g.yearLvl and
            assigned["Semester"] == g.semester and
            overlap(cand_start, cand_end, assigned_start, assigned_end)):
            print(f"❌ Block conflict: Block {g.block}, Year {g.yearLvl}, Sem {g.semester} "
                  f"at {cand['Start']}-{cand['End']} overlaps with {assigned['Code']}")
            return False

    return True

def find_instructors_for_course(course, instructors):
    course_code = course["Code"].strip().upper()
    matched = [
        i for i in instructors 
        if course_code in [c.upper() for c in i["Assignable_Courses"]]
    ]
    if not matched:
        print(f"❌ No instructor found for {course['Code']} - {course['Title']}")
    else:
        names = [i["Name"] for i in matched]
        print(f"✅ {course['Code']} matched instructors: {names}")
    return matched
