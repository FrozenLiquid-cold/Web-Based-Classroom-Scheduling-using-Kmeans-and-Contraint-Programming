import random
from .utils import *
from .scheduler import *
from copy import deepcopy

# ------------------------------
# Simple K-Means (pure Python)
# ------------------------------
def kmeans(data, k=2, max_iters=100):
    # data: list of lists [[x1, x2, x3], ...]
    # Random initial centroids
    centroids = random.sample(data, k)
    clusters = [0] * len(data)
    
    for _ in range(max_iters):
        new_clusters = []
        # Assign each point to nearest centroid
        for point in data:
            dists = [sum((p-c)**2 for p,c in zip(point, centroid)) for centroid in centroids]
            new_clusters.append(dists.index(min(dists)))
        
        if new_clusters == clusters:
            break
        clusters = new_clusters
        
        # Recompute centroids
        for i in range(k):
            assigned_points = [p for idx,p in enumerate(data) if clusters[idx]==i]
            if assigned_points:
                centroids[i] = [sum(dim)/len(dim) for dim in zip(*assigned_points)]
    return clusters

# ------------------------------
# Encode courses to numeric vectors
# ------------------------------
def encode_courses(courses, instructors, timeslots):
    vectors = []
    for c in courses:
        # Units in minutes
        units_min = int(c['Units']) * 60
        
        # Type encoding: LEC=0, LAB=1
        type_val = 0 if c['Type'].upper() == 'LEC' else 1
        
        # Number of instructors who can teach this course
        instructor_count = sum(1 for i in instructors 
                               if c['Code'].replace(" ","").lower() in i["Assignable_Courses"].replace(" ","").lower())
        
        # Day preference: ratio of available MW slots
        available_slots = [ts for ts in timeslots if int(ts['Duration_Minutes']) >= units_min]
        mw_count = sum(1 for ts in available_slots if ts['Days'] == 'MW')
        tth_count = sum(1 for ts in available_slots if ts['Days'] == 'TTh')
        total_slots = mw_count + tth_count
        day_pref = mw_count / total_slots if total_slots > 0 else 0.5  # default 0.5 if no info
        
        vectors.append([units_min, type_val, instructor_count, day_pref])
    return vectors



# ------------------------------
# create_schedule using K-Means
# ------------------------------
def create_schedule():
    courses, rooms, instructors, timeslots = load_data()
    filtered = get_courses_for_block(courses, Globals)
    
    schedule = build_schedule_with_kmeans(filtered, rooms, instructors, timeslots, max_clusters=3)
    
    print("\nGenerated Schedule:")
    
    if not schedule:
        print("❌ No valid schedule found!")
        print("\n🔹 Attempting detailed debug for each course...\n")
        for course in filtered:
            print(f"--- Debugging {course['Code']} ({course['Title']}) ---")
            _ = build_candidates(course, rooms, instructors, timeslots, [])
        input("\nPress Enter to return to the menu...")
        return

    unique_rooms = sorted(set(s['Room'] for s in schedule))
    for room_name in unique_rooms:
        print(f"\nRoom: {room_name}")
        print(generate_room_schedule(schedule, room_name))
        print("=" * 80)
    
    print("\nFull Schedule:")
    for s in schedule:
        print(f"{s['Code']} | {s['Title']} | {s['Timeslot']} | {s['Room']} | {s['Instructor']}")


def schedule_with_constraints(cluster_courses, rooms, instructors, timeslots, debug=None):
    """
    Pure Python constraint-based scheduler (no external libs).
    """
    if debug: debug.start_section("schedule_with_constraints")

    schedule = []

    # Convert to minutes helper
    def time_to_min(t):
        h, m = map(int, t.split(":"))
        return h * 60 + m

    # Check overlap between two time ranges
    def overlap(t1, t2):
        s1, e1 = map(time_to_min, t1.split("-"))
        s2, e2 = map(time_to_min, t2.split("-"))
        return not (e1 <= s2 or e2 <= s1)

    # Get slots matching course units
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
            # Same day?
            if s["Days"] == candidate["Days"]:
                # Room conflict
                if s["Room"] == candidate["Room"] and overlap(s["Time"], candidate["Time"]):
                    return False
                # Instructor conflict
                if s["Instructor"] == candidate["Instructor"] and overlap(s["Time"], candidate["Time"]):
                    return False
        return True

    # Backtracking assignment
    def assign(idx):
        if idx == len(cluster_courses):
            return True
        course = cluster_courses[idx]

        possible_slots = get_exact_slots(course)
        possible_rooms = [r for r in rooms if r["Type"].upper() == course["Type"].upper()]
        possible_instr = [i for i in instructors if course["Code"].replace(" ", "").lower()
                          in i["Assignable_Courses"].replace(" ", "").lower()]

        for room in possible_rooms:
            for instr in possible_instr:
                for seq in possible_slots:
                    start = seq[0]["Start_Time"]
                    end = seq[-1]["End_Time"]
                    days = seq[0]["Days"]

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
