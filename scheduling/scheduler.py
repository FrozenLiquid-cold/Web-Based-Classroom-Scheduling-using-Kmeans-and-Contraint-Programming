from .constraints import is_valid_assignment
from .utils import *
from globals import Globals
from data_loader import load_data

# ------------------------------
# Candidate Builders
# ------------------------------
def build_candidates(course, rooms, instructors, timeslots, current_schedule):
    """
    Generate possible assignments (instructor, room, timeslot) for a course.
    course, rooms, instructors, timeslots: list of dicts
    current_schedule: list of assigned courses
    """
    candidates = []
    course_units = int(course["Units"])

    matched_instructors = get_candidate_instructors(course, instructors)
    if not matched_instructors:
        return candidates

    candidate_rooms = get_candidate_rooms(course, rooms)
    candidate_timeslots = get_candidate_timeslots(course, timeslots)

    # Build candidates
    for ts in candidate_timeslots:
        for instr in matched_instructors:
            for room in candidate_rooms:

                # MW vs TTh balancing check
                if ts["Days"] in ["MW", "TTh"]:
                    mw_count = sum(1 for s in current_schedule if "MW" in s["Timeslot"])
                    tth_count = sum(1 for s in current_schedule if "TTh" in s["Timeslot"])
                    total = mw_count + tth_count + 1
                    if ts["Days"] == "MW" and total > 0 and (mw_count + 1) / total > 0.6:
                        continue
                    if ts["Days"] == "TTh" and total > 0 and (tth_count + 1) / total > 0.6:
                        continue

                candidates.append({
                    "Course": course["Code"],
                    "Title": course["Title"],
                    "Type": course["Type"],
                    "Instructor": instr["Name"] if isinstance(instr, dict) else instr,
                    "Room": room["Name"],
                    "Timeslot": f"{ts['Days']} {ts['Start_Time']}-{ts['End_Time']}",
                    "Slot_ID": ts["Slot_ID"]
                })

    # Special case: 3-unit courses spanning 2 consecutive slots
    if course_units == 3:
        for i in range(len(candidate_timeslots) - 1):
            ts1, ts2 = candidate_timeslots[i], candidate_timeslots[i + 1]
            if ts1["Days"] == ts2["Days"] and ts1["End_Time"] == ts2["Start_Time"]:
                total_minutes = int(ts1["Duration_Minutes"]) + int(ts2["Duration_Minutes"])
                if total_minutes >= 180:
                    for instr in matched_instructors:
                        for room in candidate_rooms:
                            candidates.append({
                                "Course": course["Code"],
                                "Title": course["Title"],
                                "Type": course["Type"],
                                "Instructor": instr["Name"] if isinstance(instr, dict) else instr,
                                "Room": room["Name"],
                                "Timeslot": f"{ts1['Days']} {ts1['Start_Time']}-{ts2['End_Time']}",
                                "Slot_ID": f"{ts1['Slot_ID']}+{ts2['Slot_ID']}"
                            })

    return candidates

# ------------------------------
# Backtracking Scheduler
# ------------------------------
def backtrack(courses, schedule, index=0, rooms=None, instructors=None, timeslots=None):
    if index >= len(courses):
        return True, schedule

    course = courses[index]
    candidates = build_candidates(course, rooms, instructors, timeslots, schedule)

    if not candidates:
        print(f"❌ No candidates for {course['Code']} {course['Title']} ({course['Type']})")
        return False, schedule

    for cand in candidates:
        if is_valid_assignment(schedule, cand, Globals):
            schedule.append(cand)
            ok, sched = backtrack(courses, schedule, index + 1, rooms, instructors, timeslots)
            if ok:
                return True, sched
            schedule.pop()
        else:
            print(f"🔎 Rejected {course['Code']} at {cand['Timeslot']} "
                  f"in {cand['Room']} with {cand['Instructor']}")

    return False, schedule

# ------------------------------
# Schedule Builder
# ------------------------------
def build_schedule(courses, rooms, instructors, timeslots):
    # Order courses by fewest candidates first (most constrained)
    courses_sorted = sorted(
        courses,
        key=lambda c: len(build_candidates(c, rooms, instructors, timeslots, []))
    )

    ok, schedule = backtrack(courses_sorted, [], 0, rooms, instructors, timeslots)
    return schedule if ok else []

def create_schedule():
    courses, rooms, instructors, timeslots = load_data()
    filtered = get_courses_for_block(courses, Globals)
    schedule = build_schedule(filtered, rooms, instructors, timeslots)

    print("\nGenerated Schedule:")
    if not schedule:
        print("No valid schedule found!")
    for s in schedule:
        print(f"{s['Course']} | {s['Title']} | {s['Timeslot']} | {s['Room']} | {s['Instructor']}")

# ------------------------------
# Helper Functions
# ------------------------------
def get_courses_for_block(courses, g):
    return [
        c for c in courses
        if c["YearLevel"] == g.yearLvl and c["Semester"] == g.semester
    ]
