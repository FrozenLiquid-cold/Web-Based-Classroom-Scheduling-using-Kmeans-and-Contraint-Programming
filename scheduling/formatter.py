def generate_room_schedule(schedule, room_name):
    """
    Converts the final schedule list into a formatted table text for a specific room.
    schedule: list of dicts like [{'Course':'CC105', 'Room':'COMP LAB 1', 'Instructor':'SAGUIN', 'Day':'M', 'Time':'7:00-7:30 AM'}]
    """

    days = ["M", "T", "W", "TH", "F"]
    times = sorted(set(entry['Time'] for entry in schedule if entry['Room'] == room_name))

    # Table header
    output = []
    output.append("JOSE RIZAL MEMORIAL STATE UNIVERSITY")
    output.append("OFFICE OF THE REGISTRAR")
    output.append("ROOM UTILIZATION")
    output.append("SECOND SEMESTER A.Y. 2024-2025\n")
    output.append(f"Room: {room_name}\n")
    output.append("------------------------------------------------------------")
    output.append("{:<13}| {:<12}| {:<12}| {:<12}| {:<12}| {:<12}".format("Time", "Mon", "Tue", "Wed", "Thu", "Fri"))
    output.append("------------------------------------------------------------")

    # Each timeslot row
    for time in times:
        row = [time]
        for day in days:
            entry = next((e for e in schedule if e['Room'] == room_name and e['Days'] == day and e['Time'] == time), None)
            if entry:
                row.append(f"{entry['Course']} ({entry['Instructor']})")
            else:
                row.append("")
        output.append("{:<13}| {:<12}| {:<12}| {:<12}| {:<12}| {:<12}".format(*row))
    return "\n".join(output)
