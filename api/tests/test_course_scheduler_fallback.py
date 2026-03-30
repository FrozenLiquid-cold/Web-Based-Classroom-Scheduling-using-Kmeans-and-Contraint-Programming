import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

course_scheduler = pytest.importorskip(
    "api.scheduler.course_scheduler",
    reason="scheduler.course_scheduler module not found",
)


def test_cluster_candidates_falls_back_when_sklearn_is_unavailable(monkeypatch):
    candidates = [
        course_scheduler.CandidateSlot(
            candidate_id=1,
            room_id=7,
            room_capacity=40,
            timeslot_id=11,
            day=1,
            start_min=420,
            end_min=510,
        ),
        course_scheduler.CandidateSlot(
            candidate_id=2,
            room_id=8,
            room_capacity=45,
            timeslot_id=12,
            day=3,
            start_min=420,
            end_min=510,
        ),
    ]

    monkeypatch.setattr(course_scheduler, "KMeans", None)
    monkeypatch.setattr(course_scheduler, "StandardScaler", None)
    monkeypatch.setattr(
        course_scheduler,
        "_SKLEARN_IMPORT_ERROR",
        ValueError("numpy.dtype size changed"),
    )

    clustered = course_scheduler._cluster_candidates(
        candidates=candidates,
        blocks_count=1,
        target_capacity=40,
    )

    assert clustered == candidates
