"""Utility script to rebuild time slot and candidate tables for the scheduler."""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.exc import SQLAlchemyError
from api import models
from db import SessionLocal, engine
from scheduler.timeslots import TIME_BLOCKS, get_time_block_minutes


YEARS: Iterable[int] = (1, 2, 3, 4)
SEMESTERS: Iterable[int] = (1, 2)


def rebuild_tables():
    """Drop and recreate the `timeslots` and `candidates` tables."""
    print("Resetting scheduler tables...")
    models.Candidate.__table__.drop(bind=engine, checkfirst=True)
    models.Timeslot.__table__.drop(bind=engine, checkfirst=True)

    models.Timeslot.__table__.create(bind=engine, checkfirst=True)
    models.Candidate.__table__.create(bind=engine, checkfirst=True)
    print("  - Fresh tables created.")


def seed_timeslots(session):
    """Populate `timeslots` with standard 30-minute blocks for each day."""
    days = session.query(models.Day).order_by(models.Day.id).all()
    if not days:
        raise RuntimeError("No entries found in `days` table — seed days first.")

    print("Seeding timeslots...")
    for day in days:
        for block in TIME_BLOCKS:
            start_min, end_min = get_time_block_minutes(block)
            slot = models.Timeslot(
                label=f"{day.label} {block['label']}",
                day=day.id,
                start_min=start_min,
                end_min=end_min,
            )
            session.add(slot)
    session.flush()
    total = session.query(models.Timeslot).count()
    print(f"  - Inserted {total} timeslots.")


def seed_candidates(session):
    """Populate `candidates` with every room-timeslot combination per course/year/semester."""
    print("Seeding candidates (this may take a moment)...")
    session.query(models.Candidate).delete()

    timeslots = session.query(models.Timeslot).order_by(models.Timeslot.id).all()
    rooms = session.query(models.Room).order_by(models.Room.id).all()
    courses = session.query(models.Course).order_by(models.Course.id).all()

    if not timeslots:
        raise RuntimeError("No timeslots available to create candidates.")
    if not rooms:
        raise RuntimeError("No rooms available to create candidates.")
    if not courses:
        raise RuntimeError("No courses available to create candidates.")

    batch = 0
    for course in courses:
        for semester in SEMESTERS:
            for year in YEARS:
                for room in rooms:
                    for slot in timeslots:
                        session.add(
                            models.Candidate(
                                course_id=course.id,
                                room_id=room.id,
                                timeslot_id=slot.id,
                                semester=semester,
                                year=year,
                            )
                        )
                        batch += 1
                        if batch % 1000 == 0:
                            session.flush()
    session.flush()
    total = session.query(models.Candidate).count()
    print(f"  - Inserted {total} candidate rows.")


def main():
    rebuild_tables()

    session = SessionLocal()
    try:
        seed_timeslots(session)
        seed_candidates(session)
        session.commit()
        print("\nDone! Scheduler tables are ready.")
    except (RuntimeError, SQLAlchemyError) as exc:
        session.rollback()
        print(f"\n✗ Error while seeding scheduler tables: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

