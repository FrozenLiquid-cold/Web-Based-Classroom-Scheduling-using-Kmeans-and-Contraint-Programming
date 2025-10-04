import os
import platform

def normalize_code(code):
    return str(code).replace(" ", "").replace("-", "").replace(".", "").upper()

def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

def parse_units(units):
    try:
        return str(int(float(str(units).replace("u", "").strip())))
    except Exception:
        return "1"

def get_candidate_timeslots(course, timeslots):
    """
    course: dict
    timeslots: list of dicts
    """
    units = parse_units(course["Units"])
    return [
        ts for ts in timeslots
        if units in str(ts["Allowed_Units"])
    ]

def get_candidate_rooms(course, rooms):
    """
    course: dict
    rooms: list of dicts
    """
    expected = (
        course["Expected_Students"]
        if "Expected_Students" in course and course["Expected_Students"]
        else 35
    )

    return [
        room for room in rooms
        if room["Capacity"] >= expected
        and room["Type"].upper() == course["Type"].upper()
    ]

def get_candidate_instructors(course, instructors):
    """
    course: dict
    instructors: list of dicts
    """
    course_code = normalize_code(course["Code"])
    possible = []

    for row in instructors:
        assignable = [normalize_code(c) for c in str(row["Assignable_Courses"]).split(",")]
        if course_code in assignable:
            possible.append(row["Name"])

    if not possible:
        print(f"⚠️ No instructor found for {course['Code']} ({course_code})")
        return []
    else:
        print(f"✅ {course['Code']} matched instructors: {possible}")
        return [row for row in instructors if row["Name"] in possible]
