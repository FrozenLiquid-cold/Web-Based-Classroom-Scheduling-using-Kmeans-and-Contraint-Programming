"""Scheduler core logic - OR-Tools constraint programming with greedy fallback"""
import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import other dependencies after setting up the path
from sqlalchemy.orm import Session
try:
    from api import models
except ImportError:
    # Fall back to relative import if absolute import fails
    from ... import models

logger = logging.getLogger(__name__)



def run_scheduler(
    db: Session,
    course_id: int,
    year: int = 1,
    *,
    years: Optional[List[int]] = None,
    semester: int,
    subject_ids: Optional[List[int]] = None,
    use_cp: bool = True,
    max_time_seconds: float = 120.0,
    use_kmeans: bool = True,
    k_clusters: int = 3,
    weight_slots: float = 2.0,
    force_refit: bool = False,
    block_capacity_overrides: Optional[List[Dict[str, Any]]] = None,
    blocks_count: Optional[int] = None,
    progress_callback: Optional[Any] = None,
) -> List[Dict]:
    """
    Generate schedules for one or more year levels using K-Means clustering
    followed by the OR-Tools CP solver (with greedy fallback).
    
    Args:
        db: Database session
        course_id: Course identifier
        year: Legacy single-year parameter (used when years is not provided)
        years: Optional list of year levels to schedule in a single run
        semester: Semester (1-2)
        subject_ids: Optional subset of subject IDs to schedule
        use_cp: Enable OR-Tools solver
        max_time_seconds: Max solver time (per cluster)
        use_kmeans: Enable K-Means pre-clustering
        k_clusters: Number of clusters for K-Means
        weight_slots: Weight multiplier for recommended slots in clustering
        force_refit: Force re-run of clustering even if cache exists
        block_capacity_overrides: Optional list of per-block capacity overrides (course_id, year, block_id, capacity)
        progress_callback: Optional callback function to report progress (accepts message string)
    
    Returns:
        Aggregated list of scheduled items covering all requested years.
    """
    import time
    
    # Helper function for progress reporting
    def report_progress(message: str) -> None:
        if progress_callback is not None:
            try:
                progress_callback(message)
            except Exception:
                pass  # Ignore callback errors
    
    report_progress("Loading course and subject data...")
    
    # Normalise years list
    if years:
        years_to_process = sorted({int(y) for y in years if y is not None})
    else:
        years_to_process = [int(year)]
    
    if not years_to_process:
        raise ValueError("No year levels provided for scheduling.")
    
    total_start = time.time()
    
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        logger.error(f"Course {course_id} not found")
        raise ValueError(f"Course {course_id} not found")
    
    college_id = course.college_id
    logger.info(
        "Scheduling course %s (college %s) for years %s, semester %s",
        course_id,
        college_id,
        years_to_process,
        semester,
    )
    
    # Pre-fetch all courses tied to this college for reuse
    college_courses = db.query(models.Course).filter(models.Course.college_id == college_id).all()
    college_course_ids = [c.id for c in college_courses]
    
    # Load all college subjects once
    college_subjects_query = db.query(models.Subject).filter(
        models.Subject.course_id.in_(college_course_ids)
    )
    # Filter by course_id if given
    if course_id:
        college_subjects_query = college_subjects_query.filter(models.Subject.course_id == course_id)

    # Filter by requested subject_ids if given
    if subject_ids:
        college_subjects_query = college_subjects_query.filter(models.Subject.id.in_(subject_ids))

    college_subjects = college_subjects_query.all()
    requested_subject_ids_filter = set(subject_ids) if subject_ids else None
    course_subjects: List[models.Subject] = []
    missing_year_subjects = 0
    seen_subject_ids: set[int] = set()
    
    years_filter = {int(y) for y in years_to_process} if years_to_process else set()
    selected_semester = int(semester)
    for subj in college_subjects:
        if subj.course_id != course_id:
            continue
        if requested_subject_ids_filter and subj.id not in requested_subject_ids_filter:
            continue
        if years_filter and subj.year_level is not None and int(subj.year_level) not in years_filter:
            continue
        if subj.semester is not None:
            try:
                subj_semester = int(subj.semester)
            except (TypeError, ValueError):
                continue
            if subj_semester != selected_semester:
                continue
        if subj.id in seen_subject_ids:
            continue
        seen_subject_ids.add(subj.id)
        course_subjects.append(subj)
        if subj.year_level is None:
            missing_year_subjects += 1
    
    if not course_subjects:
        logger.info(
            "No subjects found for course %s matching years %s and filters %s",
            course_id,
            years_to_process,
            list(requested_subject_ids_filter) if requested_subject_ids_filter else "all",
        )
        return []
    
    if missing_year_subjects:
        logger.info(
            "Detected %d subjects without year metadata for course %s; default year fallback=%s",
            missing_year_subjects,
            course_id,
            years_to_process[0],
        )
    
    course_subject_lookup = {s.id: s for s in course_subjects}
    requested_subject_ids = [s.id for s in course_subjects]
    
    block_capacity_map: Optional[Dict[Tuple[int, int, Any], int]] = None
    if block_capacity_overrides:
        block_capacity_map = {}
        for entry in block_capacity_overrides:
            # Support both dicts and Pydantic models
            if hasattr(entry, "model_dump"):
                data = entry.model_dump()
            else:
                try:
                    data = dict(entry)
                except Exception:
                    logger.warning("Skipping invalid block capacity override entry (non-dict): %s", entry)
                    continue
            try:
                key = (int(data["course_id"]), int(data["year"]), str(data["block_id"]))
                capacity = int(data["capacity"])
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skipping invalid block capacity override %s (%s)", entry, exc)
                continue
            block_capacity_map[key] = max(0, capacity)
        if not block_capacity_map:
            block_capacity_map = None
        
    # Step 1: Run K-Means clustering first (if enabled)
    if use_kmeans:
        try:
            from api.clustering.kmeans_cluster import cluster_all

            # Update subjects with missing year_level or semester metadata
            if len(years_to_process) == 1:
                target_year = years_to_process[0]
                subjects_to_update = [
                    s for s in college_subjects if s.year_level is None or s.semester is None
                ]
                for s in subjects_to_update:
                    if s.year_level is None:
                        s.year_level = target_year
                    if s.semester is None:
                        s.semester = semester
                if subjects_to_update:
                    db.commit()
                    logger.info(
                        "Updated missing metadata (year_level=%s, semester=%s) for %d subjects",
                        target_year,
                        semester,
                        len(subjects_to_update),
                    )

            cluster_start = time.time()
            run_label = "force refit" if force_refit else "full recompute"
            
            report_progress(f"🔬 Running K-Means clustering (k={k_clusters}) for {len(course_subjects)} subjects...")
            
            logger.info(
                "Running K-Means clustering (%s, k=%s) for college %s...",
                run_label,
                k_clusters,
                college_id,
            )

            # Use the new cluster_all with proper filtering
            cluster_result = cluster_all(
                db=db,
                k=k_clusters,
                course_id=course_id,
                college_id=college_id,
                year_levels=years_to_process,
                semester=semester,
                subject_ids=requested_subject_ids,
                should_cluster_rooms=True,
                weight_slots=weight_slots,
                random_state=42
            )

            cluster_elapsed = time.time() - cluster_start
            logger.info("K-Means clustering completed in %.1fs", cluster_elapsed)

            # Log subjects clustering results
            subj_res = cluster_result.get("subjects", {})
            if subj_res.get("status") == "success":
                clustered_count = subj_res.get("clustered_count", 0)
                logger.info(
                    "✅ Clustered %d subjects from college %s into %d clusters",
                    clustered_count,
                    college_id,
                    k_clusters,
                )
            else:
                logger.warning("Subject clustering failed: %s", subj_res.get("message", "Unknown error"))

            # Log rooms clustering results
            rooms_res = cluster_result.get("rooms", {})
            if rooms_res.get("status") == "success":
                clustered_count = rooms_res.get("clustered_count", 0)
                logger.info(
                    "✅ Clustered %d rooms into %d clusters",
                    clustered_count,
                    k_clusters,
                )
            else:
                logger.warning("Room clustering failed: %s", rooms_res.get("message", "Unknown error"))

        except ImportError:
            logger.warning("K-Means clustering not available (scikit-learn not installed), skipping clustering")
        except Exception as e:
            logger.error("Error during K-Means clustering: %s (continuing without clustering)", e, exc_info=True)

    
    # Step 2: Try OR-Tools CP solver
    if use_cp:
        try:
            from .cp_scheduler import run_cp_scheduler
            cp_start = time.time()
            
            report_progress(f"⚙️ Solving constraints for {len(requested_subject_ids)} subjects (max {max_time_seconds}s)...")
            
            logger.info(
                "Using OR-Tools CP solver (max_time=%.1fs) for %d subjects across years %s",
                max_time_seconds,
                len(requested_subject_ids),
                years_to_process,
            )
            
            aggregated_results = run_cp_scheduler(
                db=db,
                course_id=course_id,
                year=years_to_process[0],
                semester=semester,
                subject_ids=None,
                max_time_seconds=max_time_seconds,
                college_id=college_id,
                cluster_id_filter=None,
                years=years_to_process,
                focus_subject_ids=requested_subject_ids,
                block_capacity_overrides=block_capacity_map,
                block_count=int(blocks_count) if blocks_count is not None else 1,
                progress_callback=report_progress,
            )
            
            cp_elapsed = time.time() - cp_start
            total_elapsed = time.time() - total_start
            logger.info(
                "CP scheduler completed in %.1fs (total: %.1fs). Generated %d items for %d subjects.",
                cp_elapsed,
                total_elapsed,
                len(aggregated_results),
                len(requested_subject_ids),
            )

            allowed_subject_ids = set(requested_subject_ids)
            filtered_results = []
            unexpected_subject_ids = set()
            for item in aggregated_results:
                sid = item.get("subject_id")
                if sid in allowed_subject_ids:
                    filtered_results.append(item)
                else:
                    if sid is not None:
                        unexpected_subject_ids.add(sid)
            if unexpected_subject_ids:
                logger.warning(
                    "[CP RESULT BUG] Dropped items with unexpected subject_ids not in request: %s",
                    sorted(unexpected_subject_ids),
                )

            seen_keys = set()
            deduped_results: List[Dict[str, Any]] = []
            for item in filtered_results:
                key = (
                    item.get("subject_id"),
                    item.get("block"),
                    item.get("day_id"),
                    item.get("start_min"),
                    item.get("end_min"),
                    item.get("room_id"),
                    item.get("instructor_id"),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped_results.append(item)

            if len(deduped_results) != len(filtered_results):
                logger.info(
                    "Deduplicated CP results: %d -> %d items",
                    len(filtered_results),
                    len(deduped_results),
                )

            try:
                blocks_count_int = int(blocks_count) if blocks_count is not None else 1
            except (TypeError, ValueError):
                blocks_count_int = 1
            if blocks_count_int < 1:
                blocks_count_int = 1

            scheduled_pairs = set()
            for row in deduped_results:
                sid = row.get("subject_id")
                if sid is None:
                    continue
                block_val = row.get("block")
                block_key = str(block_val).strip() if block_val is not None else "A"
                scheduled_pairs.add((sid, block_key))

            expected_pairs = set()
            if blocks_count_int >= 2:
                for sid in allowed_subject_ids:
                    for idx in range(1, blocks_count_int + 1):
                        if idx > 26:
                            label = f"BLOCK-{idx}"
                        else:
                            label = chr(ord("A") + idx - 1)
                        expected_pairs.add((sid, label))
            else:
                for sid in allowed_subject_ids:
                    expected_pairs.add((sid, "A"))

            missing_pairs = expected_pairs - scheduled_pairs
            if missing_pairs:
                missing_subjects = {sid for (sid, _) in missing_pairs}
                logger.warning(
                    "CP+retry scheduled %d/%d requested subjects. Unscheduled subject_ids: %s",
                    len(allowed_subject_ids) - len(missing_subjects),
                    len(allowed_subject_ids),
                    sorted(missing_subjects),
                )

                # IMPORTANT: Still return placeholder rows for unscheduled subjects so the
                # frontend can display them (with empty schedule fields) for the selected
                # course/year/semester. This mirrors the greedy fallback behaviour and
                # ensures the user always sees all requested subjects.
                for sid, block_label in sorted(missing_pairs, key=lambda x: (x[0], str(x[1]))):
                    subj = course_subject_lookup.get(sid)
                    deduped_results.append({
                        "subject_id": sid,
                        "course_id": subj.course_id if subj is not None and subj.course_id is not None else course_id,
                        "year": subj.year_level if subj is not None and subj.year_level is not None else years_to_process[0],
                        "semester": subj.semester if subj is not None and subj.semester is not None else semester,
                        "day_id": None,
                        "time": None,
                        "room_id": None,
                        "instructor_id": None,
                        "block": block_label,
                    })

            return deduped_results
        except ImportError as err:
            logger.warning(
                "OR-Tools not available (ImportError: %s), falling back to greedy algorithm",
                err,
            )
        except Exception as e:
            logger.error("Error in CP solver: %s, falling back to greedy", e, exc_info=True)
            try:
                db.rollback()
            except Exception:
                logger.warning("Failed to rollback session after CP solver error", exc_info=True)
    
    # Fallback to greedy algorithm
    try:
        from .greedy import run_greedy_scheduler
        
        if not course_subjects:
            return []
        
        instructors = db.query(models.Instructor).filter(
            (models.Instructor.college_id == college_id) | (models.Instructor.college_id.is_(None))
        ).all()
        rooms = db.query(models.Room).all()
        days = db.query(models.Day).all()
        
        if not instructors or not rooms or not days:
            return []
        
        logger.info("Using greedy algorithm fallback for %d subjects", len(requested_subject_ids))
        greedy_results = run_greedy_scheduler(course_subjects, instructors, rooms, days)
        
        # Annotate greedy results with year & semester metadata
        enriched_results = []
        allowed_subject_ids = set(requested_subject_ids)
        for row in greedy_results:
            subj = course_subject_lookup.get(row.get("subject_id"))
            if not subj:
                continue
            if subj.id not in allowed_subject_ids:
                continue
            enriched_results.append({
                **row,
                "course_id": subj.course_id or course_id,
                "year": subj.year_level or years_to_process[0],
                "semester": subj.semester or semester,
            })
        
        return enriched_results
    except ImportError as err:
        logger.error("Greedy scheduler not available (ImportError: %s)", err)
        # Return empty assignments
        empty_subject_ids = set(requested_subject_ids)
        return [
            {
                "subject_id": sid,
                "course_id": (course_subject_lookup[sid].course_id if sid in course_subject_lookup else course_id),
                "year": (course_subject_lookup[sid].year_level if sid in course_subject_lookup else years_to_process[0]),
                "semester": (course_subject_lookup[sid].semester if sid in course_subject_lookup else semester),
                "day_id": None,
                "time": None,
                "room_id": None,
                "instructor_id": None,
            }
            for sid in empty_subject_ids
        ]


def save_schedule(
    db: Session,
    course_id: int,
    year: int,
    semester: int,
    schedule_items: List[Dict]
) -> List[models.Schedule]:
    """
    Save schedule to database
    
    Args:
        db: Database session
        course_id: Course ID
        year: Year level
        semester: Semester
        schedule_items: List of schedule item dicts
    
    Returns:
        List of saved Schedule models
    """
    # Delete existing schedule for this course/year/semester
    db.query(models.Schedule).filter(
        models.Schedule.course_id == course_id,
        models.Schedule.year == year,
        models.Schedule.semester == semester
    ).delete()
    
    # Create new schedule entries
    schedules = []
    logger = logging.getLogger(__name__)
    for item in schedule_items:
        # CRITICAL: Validate that we're using solver results, not subject defaults
        subject_id = item.get("subject_id")
        day_id = item.get("day_id")
        time_str = item.get("time")
        block_value = item.get("block")
        
        # Validate required fields are present
        if subject_id is None:
            logger.error(f"[SAVE BUG] Missing subject_id in schedule item: {item}")
            continue
        
        if day_id is None:
            logger.error(f"[SAVE BUG] Missing day_id for subject {subject_id} - using solver result, not subject default! Item: {item}")
            continue
        
        if not time_str:
            logger.error(f"[SAVE BUG] Missing time for subject {subject_id} - using solver result, not subject default! Item: {item}")
            continue
        
        # Log first few items to verify we're saving solver results
        if len(schedules) < 3:
            logger.info(f"[SAVE] Saving subject {subject_id}: day_id={day_id}, time={time_str}, room_id={item.get('room_id')}, instructor_id={item.get('instructor_id')}, block={block_value}")
        
        schedule = models.Schedule(
            course_id=course_id,
            year=year,
            semester=semester,
            subject_id=subject_id,
            instructor_id=item.get("instructor_id"),
            room_id=item.get("room_id"),
            day_id=day_id,  # Use solver's day_id, NOT subject default
            time=time_str,  # Use solver's time, NOT subject default
            block=str(block_value) if block_value is not None else None,
        )
        db.add(schedule)
        schedules.append(schedule)
    
    db.commit()
    
    # Refresh all schedules
    for s in schedules:
        db.refresh(s)
    
    return schedules


def load_schedule(
    db: Session,
    course_id: int,
    year: int,
    semester: int,
    instructor_id: Optional[int] = None
) -> List[models.Schedule]:
    """
    Load schedule from database using stored procedure for optimization.
    
    Args:
        db: Database session
        course_id: Course ID
        year: Year level
        semester: Semester
        instructor_id: Optional instructor ID to filter by
    
    Returns:
        List of Schedule models
    """
    # IMPORTANT: Query directly from the Schedule table so we always include
    # the latest columns (e.g., the "block" field used for A/B/C blocks).
    query = db.query(models.Schedule).filter(
        models.Schedule.course_id == course_id,
        models.Schedule.year == year,
        models.Schedule.semester == semester,
    )

    if instructor_id is not None:
        query = query.filter(models.Schedule.instructor_id == instructor_id)

    return query.all()


# Example OR-Tools implementation structure (commented out until OR-Tools is installed)
"""
def run_scheduler_ortools(
    db: Session,
    course_id: int,
    year: int,
    semester: int,
    subject_ids: Optional[List[int]] = None
) -> List[Dict]:
    \"\"\"
    Generate schedule using OR-Tools constraint programming
    
    Uncomment and implement this when OR-Tools is installed:
    pip install ortools
    \"\"\"
    from ortools.sat.python import cp_model
    
    # Load data from database
    subjects = db.query(models.Subject).all()
    if subject_ids:
        subjects = [s for s in subjects if s.id in subject_ids]
    
    instructors = db.query(models.Instructor).all()
    rooms = db.query(models.Room).all()
    days = db.query(models.Day).all()
    
    # TIME_BLOCKS are now imported from scheduler.timeslots
    from scheduler.timeslots import TIME_BLOCKS
    
    # Create the model
    model = cp_model.CpModel()
    
    # Decision variables
    # For each subject, assign: day, time slot, room, instructor
    # Example: subject_assignments[subject_id][day_id][time_idx][room_id][instructor_id] = 1 if assigned
    
    # Constraints:
    # 1. Each subject must be assigned exactly once (or not at all if no slot available)
    # 2. No room double-booking: same room, day, time can only have one subject
    # 3. No instructor double-booking: same instructor, day, time can only have one subject
    # 4. Room type must match subject type (LAB subject -> LAB room, LEC subject -> LEC room)
    # 5. Instructor preferences/constraints (if any)
    
    # Objective: Maximize number of placed subjects, minimize conflicts
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Extract solution
        generated_schedules = []
        # ... extract assignments from solver solution ...
        return generated_schedules
    else:
        # No solution found, return empty assignments
        return [{"subject_id": s.id, "day_id": None, "time": None, "room_id": None, "instructor_id": None} 
                for s in subjects]
"""
