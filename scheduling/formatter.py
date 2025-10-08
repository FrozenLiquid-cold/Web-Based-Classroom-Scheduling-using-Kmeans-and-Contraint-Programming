def generate_room_schedule(schedule, room_name):
    """
    Generate ASCII schedule table for a specific room.
    Supports MW, TTh, and F day patterns.
    """

    print(f"\nRoom: {room_name}")
    print("JOSE RIZAL MEMORIAL STATE UNIVERSITY")
    print("OFFICE OF THE REGISTRAR")
    print("ROOM UTILIZATION")
    print("SECOND SEMESTER A.Y. 2024-2025\n")

    # Define display layout
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    times = [
        "07:30-08:30", "07:30-09:30", "07:30-10:30",
        "08:30-09:30", "09:30-11:30", "13:00-15:00", "13:00-16:00"
    ]

    # Filter courses for this room
    room_sched = [s for s in schedule if s["Room"] == room_name]

    # Map each timeslot and day to a course
    table = {t: {d: "" for d in days} for t in times}

    for s in room_sched:
        course_str = f"{s['Code']} ({s['Instructor']})"
        time = s["Time"]
        day_pattern = s.get("Days", "")

        # Determine which columns (Mon/Wed/Tue/Thu/Fri) to fill
        if "MW" in day_pattern:
            for d in ["Mon", "Wed"]:
                table.setdefault(time, {}).setdefault(d, "")
                table[time][d] = course_str
        elif "TTh" in day_pattern:
            for d in ["Tue", "Thu"]:
                table.setdefault(time, {}).setdefault(d, "")
                table[time][d] = course_str
        elif day_pattern == "F":
            table.setdefault(time, {}).setdefault("Fri", "")
            table[time]["Fri"] = course_str

    # Print header
    print("------------------------------------------------------------")
    print(f"{'Time':<12} | {'Mon':<12} | {'Tue':<12} | {'Wed':<12} | {'Thu':<12} | {'Fri':<12}")
    print("------------------------------------------------------------")

    # Print each row
    for t in times:
        row = f"{t:<12} | "
        row += " | ".join(f"{table[t][d]:<12}" for d in days)
        print(row)
    print("=" * 80)