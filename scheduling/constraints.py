from datetime import datetime
from .utils import *

def parse_time_range(tstr):
    """Convert 'HH:MM-HH:MM' into (start_minutes, end_minutes)."""
    try:
        start, end = tstr.split("-")
        h1, m1 = map(int, start.split(":"))
        h2, m2 = map(int, end.split(":"))
        return h1 * 60 + m1, h2 * 60 + m2
    except Exception:
        return 0, 0


def overlap(start1, end1, start2, end2):
    """Return True if two ranges overlap."""
    return not (end1 <= start2 or end2 <= start1)

def is_valid_assignment(schedule, course, candidate):
    """
    Check if assigning this candidate causes any room/instructor/time conflict.
    """

    def parse_time_range(tstr):
        """Convert 'HH:MM-HH:MM' into (start_minutes, end_minutes)."""
        try:
            start, end = tstr.split("-")
            h1, m1 = map(int, start.split(":"))
            h2, m2 = map(int, end.split(":"))
            return h1 * 60 + m1, h2 * 60 + m2
        except Exception:
            return 0, 0

    c_days = candidate.get("Days", "")
    c_time = candidate.get("Time", "")
    c_start, c_end = parse_time_range(c_time)

    for s in schedule:
        s_days = s.get("Days", "")
        s_time = s.get("Time", "")
        s_start, s_end = parse_time_range(s_time)

        # --- check if any day overlaps (e.g., both have 'F' or 'MW')
        same_day = any(day in c_days for day in s_days) if c_days and s_days else False
        if not same_day:
            continue

        # --- check time overlap
        overlap = (c_start < s_end) and (s_start < c_end)
        if not overlap:
            continue

        # --- room conflict
        if candidate.get("Room") == s.get("Room"):
            return False

        # --- instructor conflict
        if candidate.get("Instructor") == s.get("Instructor"):
            return False

        # --- same course code LEC/LAB pairing rule
        if course.get("Code") == s.get("Code") and course.get("Type") != s.get("Type"):
            if candidate.get("Instructor") != s.get("Instructor"):
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


def schedule_with_constraints(cluster_courses, rooms, instructors, timeslots, debug=None):
    """
    Pure Python constraint-based scheduler (no external libs).
    Includes day-balance logic: 40% MW, 40% TTh, 20% F.
    """
    if debug: debug.start_section("schedule_with_constraints")

    import random
    schedule = []

    # ------------------------------
    # Helpers
    # ------------------------------
    def time_to_min(t):
        h, m = map(int, t.split(":"))
        return h * 60 + m

    def overlap(t1, t2):
        s1, e1 = map(time_to_min, t1.split("-"))
        s2, e2 = map(time_to_min, t2.split("-"))
        return not (e1 <= s2 or e2 <= s1)

    def get_exact_slots(course):
        required = int(float(course.get("Units", 1))) * 60
        seqs = []
        for i in range(len(timeslots)):
            seq = [timeslots[i]]
            total = int(timeslots[i]["Duration_Minutes"])
            for j in range(i + 1, len(timeslots)):
                if timeslots[j]["Days"] != timeslots[i]["Days"]:
                    break
                if timeslots[j]["Start_Time"] != seq[-1]["End_Time"]:
                    break
                total += int(timeslots[j]["Duration_Minutes"])
                seq.append(timeslots[j])
                if total == required:
                    seqs.append(seq)
                    break
                if total > required:
                    break
        return seqs

    def can_assign(candidate):
        for s in schedule:
            if s["Days"] == candidate["Days"]:
                if s["Room"] == candidate["Room"] and overlap(s["Time"], candidate["Time"]):
                    return False
                if s["Instructor"] == candidate["Instructor"] and overlap(s["Time"], candidate["Time"]):
                    return False
        return True

    # ------------------------------
    # Day Balancing Bias
    # ------------------------------
    def get_day_balance_weights():
        day_counts = {"MW": 0, "TTh": 0, "F": 0}
        for s in schedule:
            d = s.get("Days")
            if d in day_counts:
                day_counts[d] += 1
        total = sum(day_counts.values()) + 1
        ratios = {k: v / total for k, v in day_counts.items()}
        target = {"MW": 0.4, "TTh": 0.4, "F": 0.2}

        # Score lower if overfilled; higher if underfilled
        weights = {}
        for d in target:
            weights[d] = max(0.1, target[d] - ratios[d])
        return weights, ratios, target

    # ------------------------------
    # Backtracking Assignment
    # ------------------------------
    def assign(idx):
        if idx == len(cluster_courses):
            return True

        course = cluster_courses[idx]
        possible_slots = get_exact_slots(course)
        possible_rooms = [r for r in rooms if r["Type"].upper() == course["Type"].upper()]
        possible_instr = [
            i for i in instructors
            if course["Code"].replace(" ", "").lower() in i["Assignable_Courses"].replace(" ", "").lower()
        ]

        weights, ratios, target = get_day_balance_weights()

        # Sort slots: prioritize underused days
        possible_slots.sort(key=lambda seq: -weights.get(seq[0]["Days"], 0.1))

        # Optional: small shuffle to diversify choices
        random.shuffle(possible_slots)

        for room in possible_rooms:
            for instr in possible_instr:
                for seq in possible_slots:
                    start = seq[0]["Start_Time"]
                    end = seq[-1]["End_Time"]
                    days = seq[0]["Days"]

                    # Skip days over their ratio target
                    if ratios.get(days, 0) > target.get(days, 0) + 0.05:
                        if debug: debug.info(f"Skip {course['Code']} on {days} (over target)")
                        continue

                    cand = {
                        "Code": course["Code"],
                        "Title": course["Title"],
                        "Type": course["Type"],
                        "Room": room["Name"],
                        "Instructor": instr["Name"],
                        "Days": days,
                        "Time": f"{start}-{end}"
                    }

                    if can_assign(cand):
                        schedule.append(cand)
                        if assign(idx + 1):
                            return True
                        schedule.pop()

        return False

    assign(0)
    if debug: debug.end_section("schedule_with_constraints")
    return schedule


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


def get_courses_for_block(courses, g):
    filtered = []
    for c in courses:
        year = str(c.get("YearLevel", "")).strip()
        sem = str(c.get("Semester", "")).strip()
        prog = str(c.get("Program", "")).strip().upper()

        # Convert Globals to string for safe comparison
        if (
            year == str(g.yearLvl) and
            sem == str(g.semester) and
            prog == "BSCS"  # optional, keeps filtering by program
        ):
            filtered.append(c)
    return filtered