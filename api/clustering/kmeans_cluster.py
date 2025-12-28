"""Improved K-Means clustering for classroom scheduling"""
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from api import models

logger = logging.getLogger(__name__)


def calculate_min_max_slots(subject_type: str) -> Tuple[int, int]:
    """Calculate min and max slots based on subject type."""
    t = subject_type.upper()
    return (2, 4) if t == 'LEC' else (3, 3) if t == 'LAB' else (1, 4)


def cluster_subjects(
    db: Session,
    k: int = 3,
    course_id: Optional[int] = None,
    college_id: Optional[int] = None,
    year_levels: Optional[List[int]] = None,
    semester: Optional[int] = None,
    subject_ids: Optional[List[int]] = None,
    features: Optional[List[str]] = None,
    weight_slots: float = 2.0,
    random_state: int = 42,
) -> Dict:
    """Cluster subjects for scheduling, filtering by course/college, year, semester, and optional subject IDs."""
    from sklearn.preprocessing import StandardScaler
    from sklearn.cluster import KMeans
    import numpy as np

    if features is None:
        features = ['unit', 'year_level', 'semester', 'recommended_slots']

    # Step 1: Build base query
    query = db.query(models.Subject)

    if course_id:
        query = query.filter(models.Subject.course_id == course_id)
    elif college_id:
        course_ids = [c[0] for c in db.query(models.Course.id)
                      .filter(models.Course.college_id == college_id)
                      .all()]
        if not course_ids:
            return {"status": "error", "message": f"No courses for college_id={college_id}", "clustered_count": 0}
        query = query.filter(models.Subject.course_id.in_(course_ids))

    if subject_ids:
        query = query.filter(models.Subject.id.in_(subject_ids))

    all_subjects = query.all()

    # Step 2: Filtering by year_level and semester
    year_filter = {int(y) for y in year_levels} if year_levels else None
    semester_target = int(semester) if semester is not None else None
    requested_subject_ids_set = set(subject_ids) if subject_ids else None
    seen_ids = set()
    subjects_to_cluster = []

    for s in all_subjects:
        if s.id in seen_ids:
            continue
        if requested_subject_ids_set and s.id not in requested_subject_ids_set:
            continue
        if year_filter and s.year_level is not None and int(s.year_level) not in year_filter:
            continue
        if semester_target is not None:
            subj_sem = getattr(s, "semester", None)
            if subj_sem is None:
                continue
            try:
                subj_sem = int(subj_sem)
            except (TypeError, ValueError):
                continue
            if subj_sem != semester_target:
                continue
        subjects_to_cluster.append(s)
        seen_ids.add(s.id)

    n_subjects = len(subjects_to_cluster)
    if n_subjects == 0:
        return {"status": "error", "message": "No subjects found for clustering", "clustered_count": 0}
    if n_subjects < k:
        k = max(1, n_subjects)

    # Step 3: Prepare feature matrix
    feature_data, valid_subjects = [], []
    for s in subjects_to_cluster:
        row, valid = [], True
        for f in features:
            if f == 'unit':
                row.append(float(s.unit or 0))
            elif f == 'year_level':
                row.append(float(s.year_level or 1))
            elif f == 'semester':
                row.append(float(s.semester or 1))
            elif f == 'recommended_slots':
                row.append(float((s.recommended_slots or 1) * weight_slots))
            else:
                valid = False
                break
        if valid:
            feature_data.append(row)
            valid_subjects.append(s)

    if not feature_data:
        return {"status": "error", "message": "No valid feature data", "clustered_count": 0}

    X = StandardScaler().fit_transform(np.array(feature_data))

    # Step 4: Run K-Means
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
        kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        cluster_labels = kmeans.fit_predict(X)

    # Step 5: Assign clusters and min/max slots
    cluster_stats = {}
    lec_subject_cluster_map = {}

    for i, s in enumerate(valid_subjects):
        cid = int(cluster_labels[i])

        # Assign min/max slots
        s.min_slots, s.max_slots = (2, 4) if s.type == 'LEC' else (3, 3) if s.type == 'LAB' else (1, 4)
        if not s.recommended_slots or s.recommended_slots == 0:
            s.recommended_slots = s.min_slots

        # Track LEC cluster mapping
        if s.type.upper() == "LEC":
            lec_subject_cluster_map[s.code] = cid

        # LAB subjects inherit cluster of their LEC if exists
        if s.type.upper() == "LAB" and s.code in lec_subject_cluster_map:
            cid = lec_subject_cluster_map[s.code]
            cluster_labels[i] = cid

        s.cluster = cid

        # Track cluster stats
        if cid not in cluster_stats:
            cluster_stats[cid] = {"count": 0, "types": {}, "avg_unit": 0, "avg_slots": 0}
        cluster_stats[cid]["count"] += 1
        cluster_stats[cid]["types"][s.type] = cluster_stats[cid]["types"].get(s.type, 0) + 1

    # Step 6: Compute cluster averages
    for cid, stats in cluster_stats.items():
        cluster_subjects_list = [s for i, s in enumerate(valid_subjects) if cluster_labels[i] == cid]
        stats["avg_unit"] = float(np.mean([s.unit for s in cluster_subjects_list]))
        stats["avg_slots"] = float(np.mean([s.recommended_slots for s in cluster_subjects_list]))

    db.commit()

    return {
        "status": "success",
        "clustered_count": len(valid_subjects),
        "k": k,
        "cluster_stats": cluster_stats,
        "features_used": features
    }


def cluster_rooms(
    db: Session,
    k: int = 3,
    features: Optional[List[str]] = None,
    random_state: int = 42
) -> Dict:
    """Cluster rooms for scheduling."""
    if features is None:
        features = ['capacity', 'type_encoded']

    rooms = db.query(models.Room).all()
    n_rooms = len(rooms)
    if n_rooms == 0:
        return {"status": "error", "message": "No rooms found", "clustered_count": 0}
    if n_rooms < k:
        logger.warning(f"Reducing k from {k} to {n_rooms} due to room count")
        k = n_rooms

    feature_data, valid_rooms = [], []
    for r in rooms:
        row = []
        valid = True
        for f in features:
            if f == 'capacity':
                row.append(float(r.capacity or 30))
            elif f == 'type_encoded':
                row.append(0.0 if r.type.upper() == 'LEC' else 1.0)
            else:
                logger.warning(f"Unknown feature {f}")
                valid = False
                break
        if valid:
            feature_data.append(row)
            valid_rooms.append(r)

    if not feature_data:
        return {"status": "error", "message": "No valid feature data for rooms", "clustered_count": 0}

    X = StandardScaler().fit_transform(np.array(feature_data))
    import warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
        kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        cluster_labels = kmeans.fit_predict(X)

    cluster_stats = {}
    for i, r in enumerate(valid_rooms):
        cid = int(cluster_labels[i])
        r.cluster = cid
        if cid not in cluster_stats:
            cluster_stats[cid] = {"count": 0, "types": {}, "avg_capacity": 0}
        cluster_stats[cid]["count"] += 1
        cluster_stats[cid]["types"][r.type] = cluster_stats[cid]["types"].get(r.type, 0) + 1

    for cid, stats in cluster_stats.items():
        rooms_in_cluster = [r for i, r in enumerate(valid_rooms) if cluster_labels[i] == cid]
        stats["avg_capacity"] = float(np.mean([r.capacity or 30 for r in rooms_in_cluster]))

    db.commit()
    logger.info(f"Clustered {len(valid_rooms)} rooms into {k} clusters")
    return {"status": "success", "clustered_count": len(valid_rooms), "k": k,
            "cluster_stats": cluster_stats, "features_used": features}

def cluster_all(
    db: Session,
    k: int = 3,
    course_id: Optional[int] = None,
    college_id: Optional[int] = None,
    year_levels: Optional[List[int]] = None,
    semester: Optional[int] = None,
    subject_ids: Optional[List[int]] = None,
    should_cluster_rooms: bool = True,
    weight_slots: float = 2.0,
    random_state: int = 42
) -> Dict:
    """
    Cluster both subjects and rooms for scheduling.
    
    Subjects are filtered by course_id / college_id, year_level(s), semester, and optional subject_ids.
    Rooms are clustered independently.
    """
    results = {"subjects": None, "rooms": None}

    # Step 1: Cluster subjects
    results["subjects"] = cluster_subjects(
        db=db,
        k=k,
        course_id=course_id,
        college_id=college_id,
        year_levels=year_levels,
        semester=semester,
        subject_ids=subject_ids,
        weight_slots=weight_slots,
        random_state=random_state
    )

    # Step 2: Cluster rooms
    if should_cluster_rooms:
        # Default room features: capacity and type_encoded (0=LEC, 1=LAB)
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        import numpy as np
        import warnings

        rooms = db.query(models.Room).all()
        n_rooms = len(rooms)
        if n_rooms == 0:
            results["rooms"] = {"status": "error", "message": "No rooms found", "clustered_count": 0}
        else:
            if n_rooms < k:
                k = n_rooms

            feature_data, valid_rooms = [], []
            for r in rooms:
                try:
                    row = [float(r.capacity or 30), 0.0 if r.type.upper() == "LEC" else 1.0]
                    feature_data.append(row)
                    valid_rooms.append(r)
                except Exception:
                    continue

            if not feature_data:
                results["rooms"] = {"status": "error", "message": "No valid room feature data", "clustered_count": 0}
            else:
                X = StandardScaler().fit_transform(np.array(feature_data))
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
                    kmeans = KMeans(n_clusters=k, random_state=random_state, n_init=10)
                    cluster_labels = kmeans.fit_predict(X)

                cluster_stats = {}
                for i, r in enumerate(valid_rooms):
                    cid = int(cluster_labels[i])
                    r.cluster = cid
                    if cid not in cluster_stats:
                        cluster_stats[cid] = {"count": 0, "types": {}, "avg_capacity": 0}
                    cluster_stats[cid]["count"] += 1
                    cluster_stats[cid]["types"][r.type] = cluster_stats[cid]["types"].get(r.type, 0) + 1

                for cid, stats in cluster_stats.items():
                    rooms_in_cluster = [r for i, r in enumerate(valid_rooms) if cluster_labels[i] == cid]
                    stats["avg_capacity"] = float(np.mean([r.capacity or 30 for r in rooms_in_cluster]))

                db.commit()
                results["rooms"] = {
                    "status": "success",
                    "clustered_count": len(valid_rooms),
                    "k": k,
                    "cluster_stats": cluster_stats,
                    "features_used": ["capacity", "type_encoded"]
                }

    return results
