import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_data():
    courses = pd.read_csv(os.path.join(DATA_DIR, "Courses_CS.csv")).to_dict("records")
    rooms = pd.read_csv(os.path.join(DATA_DIR, "Rooms.csv")).to_dict("records")
    instructors = pd.read_csv(os.path.join(DATA_DIR, "Instructors_CSS.csv")).to_dict("records")
    timeslots = pd.read_csv(os.path.join(DATA_DIR, "Timeslots.csv")).to_dict("records")
    return courses, rooms, instructors, timeslots

