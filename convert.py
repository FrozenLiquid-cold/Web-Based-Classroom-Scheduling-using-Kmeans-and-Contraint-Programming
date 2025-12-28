import json

def generate_html_schedule(schedule, output_file="schedule.html"):
    # Convert Python schedule list to JSON string for JS
    schedule_json = json.dumps(schedule)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated Schedule</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
        th, td {{ border: 1px solid #333; padding: 10px; text-align: center; word-wrap: break-word; }}
        th {{ background-color: #4CAF50; color: white; }}
        td.empty {{ background-color: #f9f9f9; }}
        td.course {{ background-color: #e0f7fa; }}
    </style>
    </head>
    <body>
    <h2>Weekly Schedule</h2>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Monday</th>
                <th>Tuesday</th>
                <th>Wednesday</th>
                <th>Thursday</th>
                <th>Friday</th>
            </tr>
        </thead>
        <tbody id="schedule-body"></tbody>
    </table>

    <script>
        const schedule = {schedule_json};
        const days = ["Mon", "Tue", "Wed", "Thu", "Fri"];
        const tbody = document.getElementById("schedule-body");

        // Collect unique timeslots and sort
        const timeslots = [...new Set(schedule.map(s => s.Time))].sort();

        timeslots.forEach(time => {{
            const row = document.createElement("tr");
            const timeCell = document.createElement("td");
            timeCell.textContent = time;
            row.appendChild(timeCell);

            days.forEach(day => {{
                const cell = document.createElement("td");
                const course = schedule.find(s => s.Day === day && s.Time === time);
                if (course) {{
                    cell.className = "course";
                    cell.innerHTML = `${{course.Code}}<br>${{course.Room}}<br>${{course.Instructor}}`;
                }} else {{
                    cell.className = "empty";
                    cell.textContent = "--";
                }}
                row.appendChild(cell);
            }});

            tbody.appendChild(row);
        }});
    </script>
    </body>
    </html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Schedule HTML saved to {output_file}")
