import os
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def read_csv_to_dict_list(filepath):
    """Reads a CSV file and returns a list of dictionaries using only built-in modules."""
    with open(filepath, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        return [row for row in reader]

def load_data():
    courses = read_csv_to_dict_list(os.path.join(DATA_DIR, "Courses_CS.csv"))
    rooms = read_csv_to_dict_list(os.path.join(DATA_DIR, "Rooms.csv"))
    instructors = read_csv_to_dict_list(os.path.join(DATA_DIR, "Instructors_CSS.csv"))
    timeslots = read_csv_to_dict_list(os.path.join(DATA_DIR, "Timeslots.csv"))
    return courses, rooms, instructors, timeslots
