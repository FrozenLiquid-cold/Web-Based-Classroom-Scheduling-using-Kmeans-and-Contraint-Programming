# scheduler_with_debugger.py
# Modified scheduler with integrated Debugger
# Based on user's original file. See original for provenance. :contentReference[oaicite:1]{index=1}

import argparse
from datetime import datetime
from .constraints import is_valid_assignment,schedule_with_constraints,get_courses_for_block
from .utils import get_weighted_day
from globals import Globals
from data_loader import load_data
from scheduling.formatter import generate_room_schedule
from .clustering import *


# ------------------------------
# Candidate Builders
# ------------------------------
def build_candidates(course, rooms, instructors, timeslots, current_schedule, debug=None):
    if debug is None: debug = NullDebugger()
    debug.start_section(f"build_candidates:{course.get('Code')}")
    candidates = []
    try:
        course_units = int(course["Units"])
    except Exception as e:
        debug.error(f"Invalid Units for course {course.get('Code')}: {course.get('Units')} ({e})")
        debug.end_section(f"build_candidates:{course.get('Code')}")
        return []

    required_minutes = course_units * 60
    course_code_norm = course["Code"].replace(" ", "").lower()
    course_type = course["Type"].strip().upper()

    debug.info(f"Generating candidates for {course['Code']} ({course_type}, {course_units} units -> {required_minutes} min)")

    # --- Instructor filtering ---
    matched_instructors = []
    for instr in instructors:
        assignable = instr.get("Assignable_Courses", "").replace(" ", "").lower()
        if course_code_norm in assignable:
            matched_instructors.append(instr)
    if not matched_instructors:
        debug.warn(f"No matching instructor for {course['Code']}")
        debug.end_section(f"build_candidates:{course.get('Code')}")
        return []
    debug.info("Matched instructors:", [i.get('Name') for i in matched_instructors])

    # --- Room filtering ---
    candidate_rooms = [r for r in rooms if r.get("Type", "").strip().upper() == course_type]
    if not candidate_rooms:
        debug.warn(f"No matching room for {course['Code']} ({course_type})")
        debug.end_section(f"build_candidates:{course.get('Code')}")
        return []
    debug.info("Matched rooms:", [r.get('Name') for r in candidate_rooms])

    # --- Build valid timeslot sequences ---
    # --- Build valid timeslot sequences (exact-fit by 30-min slots) ---
    valid_ts_sequences = []

    slot_length = 30  # minutes per slot
    slots_needed = int(required_minutes / slot_length)  # e.g. 3-unit => 6 slots

    for i in range(len(timeslots)):
        seq = [timeslots[i]]
        for j in range(i + 1, len(timeslots)):
            # must stay on the same day and be consecutive
            if timeslots[j]["Days"] != timeslots[i]["Days"]:
                break

            prev_end = seq[-1]["End_Time"]
            if timeslots[j]["Start_Time"] != prev_end:
                break  # gap or overlap — stop sequence

            seq.append(timeslots[j])

            if len(seq) == slots_needed:
                valid_ts_sequences.append(seq.copy())
                break
            elif len(seq) > slots_needed:
                break

    if not valid_ts_sequences:
        debug.warn(f"No valid timeslot sequence for {course['Code']} (need {required_minutes} min)")
        debug.end_section(f"build_candidates:{course.get('Code')}")
        return []
    debug.info(f"Found {len(valid_ts_sequences)} valid timeslot sequences")

    # --- Combine instructor, room, timeslot sequence ---
    for instr in matched_instructors:
        for room in candidate_rooms:
                preferred_day = get_weighted_day()
                weighted_sequences = [seq for seq in valid_ts_sequences if preferred_day in seq[0].get("Days", "")]
                if not weighted_sequences:
                    weighted_sequences = valid_ts_sequences  # fallback

                for seq in weighted_sequences:
                    days = seq[0].get("Days")
                    start = seq[0].get("Start_Time")
                    end = seq[-1].get("End_Time")


                # --- Balance days: 40% MW, 40% TTh, 20% F ---
                mw_count = sum(1 for s in current_schedule if "MW" in s.get("Timeslot", ""))
                tth_count = sum(1 for s in current_schedule if "TTh" in s.get("Timeslot", ""))
                f_count = sum(1 for s in current_schedule if s.get("Timeslot", "").startswith("F"))
                total = mw_count + tth_count + f_count + 1  # +1 for this candidate

                # target ratios
                target = {"MW": 0.4, "TTh": 0.4, "F": 0.2}
                ratios = {
                    "MW": mw_count / total if total > 0 else 0,
                    "TTh": tth_count / total if total > 0 else 0,
                    "F": f_count / total if total > 0 else 0,
                }

                            # --- Balance + Weighted Bias ---
                target = {"MW": 0.4, "TTh": 0.4, "F": 0.2}
                ratios = {
                    "MW": mw_count / total if total > 0 else 0,
                    "TTh": tth_count / total if total > 0 else 0,
                    "F": f_count / total if total > 0 else 0,
                }

                # pruning still applies when over-limit
                if ratios.get(days, 0) > target.get(days, 0) + 0.05:
                    debug.info(f"Pruned {course['Code']} on {days} (MW={mw_count}, TTh={tth_count}, F={f_count})")
                    continue

                # weight factor = how far below target
                weight_factor = max(0.1, target[days] - ratios[days])  # minimum 0.1 to avoid zero
                candidate = {
                    "Code": course["Code"],
                    "Title": course.get("Title"),
                    "Type": course.get("Type"),
                    "Instructor": instr.get("Name"),
                    "Room": room.get("Name"),
                    "Timeslot": f"{days} {start}-{end}",
                    "Days": days,
                    "Time": f"{start}-{end}",
                    "Slot_ID": "+".join(ts.get("Slot_ID", "") for ts in seq),
                    "Weight": weight_factor,  # ⬅️ bias toward underfilled day
                }
                candidates.append(candidate)


                candidate = {
                    "Code": course["Code"],
                    "Title": course.get("Title"),
                    "Type": course.get("Type"),
                    "Instructor": instr.get("Name"),
                    "Room": room.get("Name"),
                    "Timeslot": f"{days} {start}-{end}",
                    "Days": days,              # <-- add this
                    "Time": f"{start}-{end}",  # <-- and this
                    "Slot_ID": "+".join(ts.get("Slot_ID", "") for ts in seq)
                }

                candidates.append(candidate)

    if not candidates:
        debug.warn(f"No valid candidates after combination for {course['Code']}")
    else:
        debug.info(f"Total candidates for {course['Code']}: {len(candidates)}")

    # Optionally show a small sample when verbose
    if not debug.brief:
        for i, c in enumerate(candidates[:10]):
            debug.log(f"Candidate #{i+1}", c)

    debug.end_section(f"build_candidates:{course.get('Code')}")
    return candidates

# ------------------------------
# Backtracking Scheduler
# ------------------------------
def backtrack(courses, schedule, index, rooms, instructors, timeslots, debug=None):
    if debug is None: debug = NullDebugger()
    if index == len(courses):
        debug.info("All courses assigned; finishing backtrack.")
        return True, schedule  # all assigned

    course = courses[index]
    debug.start_section(f"backtrack_course:{course.get('Code')}_idx{index}")
    debug.info(f"Backtracking: index={index}, course={course.get('Code')}")

    candidates = build_candidates(course, rooms, instructors, timeslots, schedule, debug=debug)
    # --- Prioritize candidates by day balance weight ---
    candidates.sort(key=lambda c: c.get("Weight", 1.0), reverse=True)


    for cand in candidates:
        debug.info(f"Trying candidate for {course.get('Code')}: {cand['Timeslot']} | {cand['Room']} | {cand['Instructor']}")
        if is_valid_assignment(schedule, course, cand):
            schedule.append(cand)
            debug.log("Assigned:", cand)
            ok, result = backtrack(courses, schedule, index + 1, rooms, instructors, timeslots, debug=debug)
            if ok:
                debug.end_section(f"backtrack_course:{course.get('Code')}_idx{index}")
                return True, result
            # undo assignment
            popped = schedule.pop()
            debug.log("Backtracked (removed):", popped)
        else:
            debug.info("Candidate invalid by constraints:", cand)
    debug.warn(f"No candidate worked for {course.get('Code')} at index {index}")
    debug.end_section(f"backtrack_course:{course.get('Code')}_idx{index}")
    return False, schedule

# ------------------------------
# K-Means helpers (unchanged logic, with optional debug)
# ------------------------------


# ------------------------------
# Schedule Builder with K-Means
# ------------------------------
def build_schedule_with_kmeans(courses, rooms, instructors, timeslots, max_clusters=3, debug=None):
    if debug is None:
        debug = NullDebugger()

    debug.start_section("build_schedule_with_kmeans")

    vectors = encode_courses(courses, instructors, timeslots)
    k = min(max_clusters, len(courses))
    if k <= 0:
        debug.warn("No clusters to build (no courses).")
        debug.end_section("build_schedule_with_kmeans")
        return []

    cluster_labels = kmeans(vectors, k=k)
    debug.info("Cluster labels:", cluster_labels)

    schedule = []

    for cluster_id in range(k):
        cluster_courses = [c for i, c in enumerate(courses) if cluster_labels[i] == cluster_id]
        debug.info(f"Scheduling cluster {cluster_id} with constraint propagation")

        # 🔹 Run the constraint-based scheduler for this cluster
        cluster_schedule = schedule_with_constraints(cluster_courses, rooms, instructors, timeslots, debug=debug)

        if cluster_schedule:
            debug.log(f"Cluster {cluster_id}: scheduled {len(cluster_schedule)} courses successfully.")
            schedule.extend(cluster_schedule)
        else:
            debug.warn(f"Cluster {cluster_id} produced no valid schedule; using fallback (per-course greedy).")

            # 🔸 Fallback: Greedy assignment if constraint-scheduler failed
        for c in cluster_courses:
            candidates = build_candidates(c, rooms, instructors, timeslots, schedule, debug=debug)
            if not candidates:
                debug.warn(f"No candidate slots found for {c['Code']} ({c['Title']}).")
                continue

            # 🔹 Sort candidates by weight (bias towards underfilled day)
            candidates.sort(key=lambda x: x.get("Weight", 1.0), reverse=True)

            for cand in candidates:
                if is_valid_assignment(schedule, c, cand):
                    schedule.append(cand)
                    debug.log(f"Placed {c['Code']} ({c['Title']}) via weighted fallback ({cand['Days']}).")
                    break

                else:
                    debug.warn(f"No candidate slots found for {c['Code']} ({c['Title']}).")

    debug.end_section("build_schedule_with_kmeans")
    return schedule

# ------------------------------
# Main Schedule Creation
# ------------------------------
def create_schedule(debug=None):
    if debug is None: debug = NullDebugger()
    debug.start_section("create_schedule")
    courses, rooms, instructors, timeslots = load_data()
    filtered = get_courses_for_block(courses, Globals)

    debug.info(f"Loaded data: courses={len(filtered)}, rooms={len(rooms)}, instructors={len(instructors)}, timeslots={len(timeslots)}")

    schedule = build_schedule_with_kmeans(filtered, rooms, instructors, timeslots, max_clusters=3, debug=debug)

    debug.log("Generated schedule length:", len(schedule))
    if not schedule:
        debug.error("No valid schedule found!")
        debug.info("Attempting detailed debug for each course...")
        for course in filtered:
            debug.start_section(f"debug_course_build:{course.get('Code')}")
            _ = build_candidates(course, rooms, instructors, timeslots, [], debug=debug)
            debug.end_section(f"debug_course_build:{course.get('Code')}")
        debug.save()
        debug.end_section("create_schedule")
        return []

    # Generate schedule ASCII for each room
    unique_rooms = sorted(set(s['Room'] for s in schedule))
    for room_name in unique_rooms:
        debug.info(f"Room: {room_name}")
        try:
            print(generate_room_schedule(schedule, room_name))
        except Exception as e:
            debug.error("Error generating room schedule for", room_name, ":", e)

    debug.info("Full Schedule:")
    for s in schedule:
        debug.log(f"{s['Code']} | {s['Title']} | {s['Timeslot']} | {s['Room']} | {s['Instructor']}")

    debug.save()
    debug.end_section("create_schedule")
    return schedule

# ------------------------------
# Additional debug helper
# ------------------------------


# ------------------------------
# CLI
# ------------------------------
def main_cli():
    parser = argparse.ArgumentParser(description="Scheduler with integrated debugger")
    parser.add_argument("--debug", action="store_true", help="Enable console debug output (verbose)")
    parser.add_argument("--brief", action="store_true", help="Less verbose debug messages")
    parser.add_argument("--log", type=str, help="Optional debug log file to append")
    parser.add_argument("--dump-course", type=str, help="Dump candidate debug for a specific course code and exit")
    args = parser.parse_args()

    if args.debug or args.log:
        dbg = Debugger(enable_console=args.debug, filename=args.log, brief=args.brief)
    else:
        dbg = NullDebugger()

    if args.dump_course:
        dump_course_debug(args.dump_course, debug=dbg)
        if hasattr(dbg, "save"): dbg.save()
        return

    schedule = create_schedule(debug=dbg)
    if not schedule:
        if args.debug:
            print("Scheduler finished with no schedule. Check debug logs above or the file provided with --log.")
        else:
            print("No schedule found. Re-run with --debug for details.")
    else:
        print(f"Schedule created with {len(schedule)} entries.")

if __name__ == "__main__":
    main_cli()


# ------------------------------
# create_schedule using K-Means
def create_schedule():
    courses, rooms, instructors, timeslots = load_data()
    filtered = get_courses_for_block(courses, Globals)
    schedule = build_schedule_with_kmeans(filtered, rooms, instructors, timeslots)

    if not schedule:
        print("No valid schedule found!")
        return []

    # Optionally print to console
    print("\nFull Schedule:")
    for s in schedule:
        print(f"{s['Code']} | {s['Title']} | {s['Time']} | {s['Room']} | {s['Instructor']}")
    
    return schedule

def dump_course_debug(course_code, debug=None):
    if debug is None: debug = NullDebugger()
    courses, rooms, instructors, timeslots = load_data()
    found = next((c for c in courses if c.get("Code")==course_code or c.get("Code").replace(" ","")==course_code.replace(" ","")), None)
    if not found:
        debug.error("Course not found:", course_code)
        return
    debug.start_section(f"dump_course_debug:{course_code}")
    _ = build_candidates(found, rooms, instructors, timeslots, [], debug=debug)
    debug.end_section(f"dump_course_debug:{course_code}")