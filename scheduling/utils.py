import os
import platform
import random
from datetime import datetime
from data_loader import *


DAY_WEIGHTS = {
    "Mon": 0.2,  # 40% spread across Mon+Wed (0.2 + 0.2)
    "Tue": 0.2,  # 40% spread across Tue+Thu
    "Wed": 0.2,
    "Thu": 0.2,
    "Fri": 0.2   # 20% Friday
}

def get_weighted_day():
    """
    Returns a day group ('MW', 'TTh', or 'F') using weighted probability.
    40% MW, 40% TTh, 20% F.
    """
    days = ['MW', 'TTh', 'F']
    weights = [0.4, 0.4, 0.2]  # 40/40/20
    return random.choices(days, weights=weights, k=1)[0]


class NullDebugger:
    def __init__(self):
        self.brief = False  # Prevent AttributeError when accessed
    def log(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warn(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def start_section(self, name): pass
    def end_section(self, name): pass
    def save(self): pass

class Debugger:
    def __init__(self, enable_console=True, filename=None, brief=False):
        self.enable_console = enable_console
        self.filename = filename
        self.brief = brief
        self.lines = []
        self.start_time = datetime.now()

    def _write(self, level, *parts):
        t = datetime.now().strftime("%H:%M:%S")
        msg = f"[{t}] [{level}] " + " ".join(str(p) for p in parts)
        if self.enable_console:
            print(msg)
        if self.filename:
            self.lines.append(msg + "\n")

    def log(self, *parts): self._write("LOG", *parts)
    def info(self, *parts): 
        if not self.brief: 
            self._write("INFO", *parts)
    def warn(self, *parts): self._write("WARN", *parts)
    def error(self, *parts): self._write("ERROR", *parts)

    def start_section(self, name):
        self._write("SECTION", f"START {name}")

    def end_section(self, name):
        self._write("SECTION", f"END {name}")

    def save(self):
        if not self.filename:
            return
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(f"\n--- Debug session started at {self.start_time.isoformat()} ---\n")
            f.writelines(self.lines)
            f.write(f"--- End session ({datetime.now().isoformat()}) ---\n\n")
        self.lines = []

            

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
    






def get_day_balance(schedule):
    """Returns a dictionary counting how many timeslots exist per day."""
    balance = {"MW": 0, "TTh": 0, "F": 0}
    for s in schedule:
        if "MW" in s["Timeslot"]:
            balance["MW"] += 1
        elif "TTh" in s["Timeslot"]:
            balance["TTh"] += 1
        elif "F" in s["Timeslot"]:
            balance["F"] += 1
    return 



def generate_html_schedule(schedule, output_file="schedule.html"):
    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    # Collect all unique timeslots
    timeslots = sorted({s["Timeslot"].split()[1] for s in schedule})

    # Build a grid: grid[time][day] = course info
    from collections import defaultdict
    grid = defaultdict(dict)
    for s in schedule:
        day, time = s["Timeslot"].split()
        grid[time][day] = f"{s['Code']}<br>{s['Room']}<br>{s['Instructor']}"

    # Start HTML
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Schedule</title>
<style>
body { font-family: Arial, sans-serif; padding: 20px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #333; padding: 8px; text-align: center; }
th { background-color: #4CAF50; color: white; }
td.empty { background-color: #f9f9f9; }
td.course { background-color: #e0f7fa; }
</style>
</head>
<body>
<h2>Generated Schedule</h2>
<table>
<thead>
<tr>
<th>Time</th>"""
    for day in days:
        html += f"<th>{day}</th>"
    html += "</tr>\n</thead>\n<tbody>\n"

    # Fill table rows
    for time in timeslots:
        html += f"<tr><td>{time}</td>"
        for day in days:
            cell = grid[time].get(day, "")
            if cell:
                html += f'<td class="course">{cell}</td>'
            else:
                html += '<td class="empty"></td>'
        html += "</tr>\n"

    html += "</tbody>\n</table>\n</body>\n</html>"

    # Write to file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Schedule saved to {output_file}")
