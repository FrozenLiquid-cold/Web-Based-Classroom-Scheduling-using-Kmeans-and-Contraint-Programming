import os
import platform
from datetime import datetime
from data_loader import *
from .scheduler import build_candidates


class NullDebugger:
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