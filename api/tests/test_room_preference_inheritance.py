import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

cp_scheduler = pytest.importorskip(
    "scheduler.cp_scheduler",
    reason="scheduler.cp_scheduler module not found",
)


@dataclass
class Subject:
    id: int
    course_id: int
    code: str
    type: str


@dataclass
class Course:
    id: int
    college_id: int


@dataclass
class Room:
    id: int
    type: str
    building_id: int = None


@dataclass
class SubjectRoomPreference:
    subject_id: int
    room_id: int


@dataclass
class Building:
    id: int
    college_id: int = None
    is_shared: bool = False


class FakeQuery:
    def __init__(self, model, data):
        self.model = model
        self.data = data

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.data)

    def get(self, key):
        for item in self.data:
            if getattr(item, "id", None) == key:
                return item
        return None

    def first(self):
        rows = self.all()
        return rows[0] if rows else None


class FakeDB:
    def __init__(self, mapping):
        self.mapping = mapping

    def query(self, model):
        return FakeQuery(model, self.mapping.get(model, []))


def test_build_eligibility_maps_inherits_room_prefs_by_code_and_type(monkeypatch):
    subjects = [
        Subject(id=7, course_id=4, code="CC 102", type="LAB"),
        Subject(id=8, course_id=4, code="CC 102", type="LEC"),
    ]
    rooms = [
        Room(id=4, type="LAB"),
        Room(id=8, type="LEC"),
    ]

    fake_db = FakeDB(
        {
            cp_scheduler.models.Course: [Course(id=4, college_id=4)],
            cp_scheduler.models.Subject: subjects,
            cp_scheduler.models.SubjectRoomPreference: [
                SubjectRoomPreference(subject_id=7, room_id=4)
            ],
            cp_scheduler.models.Building: [],
        }
    )

    monkeypatch.setattr(
        cp_scheduler.db_procedures,
        "get_instructor_eligibility",
        lambda db, subject_id: [],
    )
    monkeypatch.setattr(
        cp_scheduler.db_procedures,
        "get_room_eligibility",
        lambda db, subject_id: [],
    )

    _, subject_to_all_rooms, _ = cp_scheduler.build_eligibility_maps(
        subjects=subjects,
        instructors=[],
        rooms=rooms,
        db=fake_db,
    )

    assert subject_to_all_rooms[7] == [4]
    assert subject_to_all_rooms[8] == [8]


def test_build_eligibility_maps_discards_shared_room_prefs_for_regular_subjects(monkeypatch):
    subjects = [
        Subject(id=18, course_id=4, code="CC 102", type="LEC"),
    ]
    rooms = [
        Room(id=8, type="LEC", building_id=1),
        Room(id=32, type="LEC", building_id=2),
    ]

    fake_db = FakeDB(
        {
            cp_scheduler.models.Course: [Course(id=4, college_id=4)],
            cp_scheduler.models.Subject: subjects,
            cp_scheduler.models.SubjectRoomPreference: [
                SubjectRoomPreference(subject_id=18, room_id=32)
            ],
            cp_scheduler.models.Building: [
                Building(id=1, college_id=4, is_shared=False),
                Building(id=2, college_id=4, is_shared=True),
            ],
        }
    )

    monkeypatch.setattr(
        cp_scheduler.db_procedures,
        "get_instructor_eligibility",
        lambda db, subject_id: [],
    )
    monkeypatch.setattr(
        cp_scheduler.db_procedures,
        "get_room_eligibility",
        lambda db, subject_id: [],
    )

    _, subject_to_all_rooms, subject_to_preferred_rooms = cp_scheduler.build_eligibility_maps(
        subjects=subjects,
        instructors=[],
        rooms=rooms,
        db=fake_db,
    )

    assert subject_to_preferred_rooms[18] == []
    assert subject_to_all_rooms[18] == [8]
