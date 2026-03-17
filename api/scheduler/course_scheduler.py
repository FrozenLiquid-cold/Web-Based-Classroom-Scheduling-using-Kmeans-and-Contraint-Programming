"""Course-scoped scheduling workflow using K-Means + CP-SAT."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple, Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ortools.sat.python import cp_model

from .. import models

logger = logging.getLogger(__name__)

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    _SKLEARN_IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:  # pragma: no cover - depends on local Python wheels
    KMeans = None
    StandardScaler = None
    _SKLEARN_IMPORT_ERROR = exc


@dataclass
class CandidateSlot:
    """Single candidate (room, timeslot) offer that can host one block of a course."""

    candidate_id: int
    room_id: int
    room_capacity: int
    timeslot_id: int
    day: int
    start_min: int
    end_min: int


def _load_course_and_candidates(
    session: Session,
    course_id: int,
    year: int,
    semester: int,
) -> Tuple[models.Course, List[CandidateSlot], Dict[str, Any]]:
    """Fetch course metadata, candidate slots, and existing bookings."""

    course = session.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise ValueError(f"Course {course_id} not found")

    candidate_rows: Sequence[models.Candidate] = (
        session.query(models.Candidate)
        .join(models.Room, models.Candidate.room_id == models.Room.id)
        .join(models.Timeslot, models.Candidate.timeslot_id == models.Timeslot.id)
        .filter(
            models.Candidate.course_id == course_id,
            models.Candidate.semester == semester,
            models.Candidate.year == year,
        )
        .all()
    )

    candidates: List[CandidateSlot] = []
    for row in candidate_rows:
        candidates.append(
            CandidateSlot(
                candidate_id=row.id,
                room_id=row.room_id,
                room_capacity=(row.room.capacity or 0),
                timeslot_id=row.timeslot_id,
                day=row.timeslot.day,
                start_min=row.timeslot.start_min,
                end_min=row.timeslot.end_min,
            )
        )

    existing_room_assignments = {
        (sched.room_id, sched.day_id, sched.time)
        for sched in session.query(models.Schedule).filter(
            and_(
                models.Schedule.semester == semester,
                models.Schedule.year == year,
            )
        )
        if sched.room_id and sched.day_id and sched.time
    }

    return course, candidates, {"existing_room_assignments": existing_room_assignments}


def _cluster_candidates(
    candidates: List[CandidateSlot],
    blocks_count: int,
    target_capacity: Optional[int],
    n_clusters: int = 4,
) -> List[CandidateSlot]:
    """Cluster candidates by capacity/day/start and pick the cluster closest to course demand."""

    if not candidates:
        return []
    if KMeans is None or StandardScaler is None:
        logger.warning(
            "scikit-learn unavailable in course_scheduler (%s). "
            "Falling back to unclustered candidate selection.",
            _SKLEARN_IMPORT_ERROR,
        )
        return candidates

    feature_matrix = [
        [cand.room_capacity, cand.day, cand.start_min] for cand in candidates
    ]
    scaler = StandardScaler()
    X = scaler.fit_transform(feature_matrix)

    n_clusters = min(max(1, n_clusters), len(candidates))
    if n_clusters == 1:
        return candidates

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = kmeans.fit_predict(X)

    clusters: Dict[int, List[CandidateSlot]] = {}
    for cand, label in zip(candidates, labels):
        clusters.setdefault(label, []).append(cand)

    target_capacity = target_capacity or 0
    best_label = None
    best_score = float("inf")

    for label, cluster in clusters.items():
        if len(cluster) < blocks_count:
            continue
        avg_capacity = sum(slot.room_capacity for slot in cluster) / len(cluster)
        capacity_gap = abs(avg_capacity - target_capacity)
        if capacity_gap < best_score:
            best_score = capacity_gap
            best_label = label

    if best_label is None:
        return candidates

    return clusters[best_label]


def _solve_with_cp(
    course: models.Course,
    candidates: List[CandidateSlot],
    existing_room_assignments: set[Tuple[int, int, str]],
    blocks_count: int,
) -> List[CandidateSlot]:
    """Solve for non-conflicting candidate assignments using CP-SAT."""

    if len(candidates) < blocks_count:
        return []

    model = cp_model.CpModel()
    solver = cp_model.CpSolver()

    x_vars: Dict[int, cp_model.IntVar] = {}
    for idx, cand in enumerate(candidates):
        x_vars[idx] = model.NewBoolVar(f"cand_{cand.candidate_id}")

    model.Add(sum(x_vars.values()) == blocks_count)

    for idx, cand in enumerate(candidates):
        time_label = f"{cand.start_min}-{cand.end_min}"
        if (cand.room_id, cand.day, time_label) in existing_room_assignments:
            model.Add(x_vars[idx] == 0)

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            cand_i = candidates[i]
            cand_j = candidates[j]
            same_room = cand_i.room_id == cand_j.room_id
            same_day = cand_i.day == cand_j.day
            overlap = not (
                cand_i.end_min <= cand_j.start_min
                or cand_j.end_min <= cand_i.start_min
            )
            if same_room and same_day and overlap:
                model.Add(x_vars[i] + x_vars[j] <= 1)

    target_capacity = getattr(course, "capacity", 0) or 0
    slack_terms = []
    for idx, cand in enumerate(candidates):
        slack = max(0, cand.room_capacity - target_capacity)
        slack_terms.append(slack * x_vars[idx])
    model.Minimize(sum(slack_terms))

    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = 42
    solver.parameters.cp_model_presolve = True

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []

    chosen: List[CandidateSlot] = []
    for idx, cand in enumerate(candidates):
        if solver.BooleanValue(x_vars[idx]):
            chosen.append(cand)

    return chosen


def schedule_course_refactored(
    session: Session,
    course_id: int,
    year: int,
    semester: int,
    blocks_count: int,
) -> Dict[str, Any]:
    """End-to-end orchestration for course-specific scheduling."""

    (
        course,
        candidates,
        context,
    ) = _load_course_and_candidates(session, course_id, year, semester)

    clustered = _cluster_candidates(
        candidates,
        blocks_count,
        getattr(course, "capacity", None),
    )

    chosen = _solve_with_cp(
        course,
        clustered,
        context["existing_room_assignments"],
        blocks_count,
    )

    if not chosen:
        return {
            "status": "no_feasible_schedule",
            "course_id": course_id,
            "year": year,
            "semester": semester,
            "blocks_requested": blocks_count,
            "scheduled": [],
        }

    session.query(models.Schedule).filter(
        models.Schedule.course_id == course_id,
        models.Schedule.year == year,
        models.Schedule.semester == semester,
    ).delete()

    response_rows: List[Dict[str, Any]] = []
    for slot in chosen:
        timeslot = (
            session.query(models.Timeslot)
            .filter(models.Timeslot.id == slot.timeslot_id)
            .first()
        )

        schedule_row = models.Schedule(
            course_id=course_id,
            subject_id=None,
            instructor_id=None,
            room_id=slot.room_id,
            day_id=slot.day,
            time=f"{slot.start_min}-{slot.end_min}",
            year=year,
            semester=semester,
        )
        session.add(schedule_row)

        response_rows.append(
            {
                "room_id": slot.room_id,
                "timeslot_id": slot.timeslot_id,
                "day": slot.day,
                "start_min": slot.start_min,
                "end_min": slot.end_min,
                "start_time": getattr(timeslot, "label", None),
            }
        )

    session.commit()

    return {
        "status": "scheduled",
        "course_id": course_id,
        "year": year,
        "semester": semester,
        "blocks_requested": blocks_count,
        "scheduled": response_rows,
    }

