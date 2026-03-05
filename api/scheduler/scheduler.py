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
from sqlalchemy.orm import Session, joinedload
import re
from collections import defaultdict
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
) -> Tuple[List[Dict], Dict[int, Dict]]:
    """
    Generate schedules for one or more year levels using K-Means clustering
    followed by the OR-Tools CP solver (with greedy fallback).

    Returns:
        Tuple of (Aggregated list of scheduled items, Dict of scheduling diagnostics)
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
        return [], {}
    
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
            
            report_progress(f"Running K-Means clustering (k={k_clusters}) for {len(course_subjects)} subjects...")
            
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
            
            # LOAD EXISTING BOOKINGS
            # Detect booking from other courses/years to prevent inter-run conflicts
            logger.info("Loading existing bookings to prevent conflicts...")
            
            # Fetch all schedules for this semester
            # We want to BLOCK everything except what we are currently regenerating
            existing_schedules = db.query(models.Schedule).filter(
                models.Schedule.semester == semester
            ).options(joinedload(models.Schedule.room)).all()
            
            booked_room_ranges = defaultdict(list)
            booked_instr_ranges = defaultdict(list)
            
            years_set = set(years_to_process)
            regenerating_count = 0
            blocking_count = 0
            
            # Load time utilities
            from .timeslots import TIME_BLOCKS, time_to_minutes
            
            # Helper to normalize time strings for matching (handle different dash types)
            def normalize_time_str(s):
                if not s: return ""
                return s.replace("–", "-").replace("—", "-").replace(" ", "").upper()

            # Create lookup map for normalized time labels -> (start_min, end_min)
            # We map standard block labels to their true minute ranges
            block_lookup = {}
            for tb in TIME_BLOCKS:
                # Store normalized label matches (e.g. "2:30-4:00")
                norm_label = normalize_time_str(tb['label'])
                start_m = time_to_minutes(tb['start'])
                end_m = time_to_minutes(tb['end'])
                block_lookup[norm_label] = (start_m, end_m)

                # Store 24-hour implicit matches (e.g. "14:30-16:00")
                # Because DB might store "14:30-16:00" which doesn't match label "2:30-4:00"
                start_24 = tb['start'].strip() # "14:30"
                end_24 = tb['end'].strip()     # "16:00"
                label_24 = f"{start_24}-{end_24}"
                label_24_norm = normalize_time_str(label_24)
                block_lookup[label_24_norm] = (start_m, end_m)

                # Also try single-digit hour variant if strictly "07:00" -> "7:00"
                if start_24.startswith("0"):
                    label_24_short = f"{start_24[1:]}-{end_24}"
                    block_lookup[normalize_time_str(label_24_short)] = (start_m, end_m)

            for sched in existing_schedules:
                # SKIP if this schedule is being regenerated in the current run
                # (Same course AND same year level)
                if sched.course_id == course_id and sched.year in years_set:
                    regenerating_count += 1
                    continue
                
                blocking_count += 1
                
                # Parse existing booking using ROBUST block matching
                if not sched.time: continue
                
                # sched.time is like "M 7:30–9:00 LAB"
                # We want to find which block label appears in this string
                matched_range = None
                sched_time_norm = normalize_time_str(sched.time)
                
                # Check for exact block matches
                for label_norm, (s_min, e_min) in block_lookup.items():
                    if label_norm in sched_time_norm:
                        matched_range = (s_min, e_min)
                        break
                
                if not matched_range:
                    # Fallback: Parse distinct times found in string using regex
                    # This works for "14:30-16:00" (24h) and "4:00 PM - 7:00 AM" (12h)
                    # For "1:00 - 2:30", we need heuristic (1:00 is PM)
                    try:
                        # Find all HH:MM patterns
                        import re
                        times = re.findall(r'(\d{1,2}):(\d{2})', sched.time)
                        if len(times) >= 2:
                            # Take first and second (start/end)
                            h1, m1 = map(int, times[0])
                            h2, m2 = map(int, times[1])
                            
                            def normalize_mins(h, m):
                                # Heuristic: School runs 7am to 9pm.
                                # If hour < 7, it's PM (13:00 - 18:00 mapping from 1-6)
                                # 12 is 12 PM (noon)
                                if h < 7: h += 12
                                elif h == 12: pass # 12:00 is noon
                                # If explicitly PM in string? 
                                # This heuristic is primarily for "1:00-2:30" format without AM/PM labels
                                # But if string has "PM", purely numeric parse ignores it.
                                # However, DB usually uses 24h or labels.
                                return h * 60 + m
                            
                            s_min = normalize_mins(h1, m1)
                            e_min = normalize_mins(h2, m2)
                            
                            # Correction: if "11:30 - 1:00", s=690, e=60 (converted to 780 by heuristic? No, 1 < 7 -> 13)
                            # 11:30 -> 11 >= 7 -> 11:30 AM.
                            # 1:00 -> 1 < 7 -> 1:00 PM.
                            # Works!
                            
                            # What if "7:00 PM"? 7 >= 7. Treated as 7:00 AM? 
                            # If "PM" is present in string, we should respect it.
                            # Rudimentary PM check:
                            if "PM" in sched.time.upper() and s_min < 720 and h1 < 12:
                                s_min += 720
                            if "PM" in sched.time.upper() and e_min < 720 and h2 < 12:
                                e_min += 720
                                
                            blocked_range = (s_min, e_min, {
                                "course_id": sched.course_id,
                                "year": sched.year,
                                "subject_id": sched.subject_id,
                                "description": f"Course {sched.course_id} Year {sched.year}"
                            })
                            
                            # Append
                            if s_min < e_min:
                                if sched.room_id and sched.room:
                                    key = (sched.room.name, sched.day_id)
                                    booked_room_ranges[key].append(blocked_range)
                                    
                                    # DEBUG: Log if we are blocking any GS ER room
                                    if "GS ER" in str(sched.room.name):
                                        logger.info(f"[SCHEDULER FILTER] Blocking {sched.room.name} (ID {sched.room_id}) Day {sched.day_id}: {sched.time} -> {blocked_range}. SubjID={sched.subject_id}, Year={sched.year}, Course={sched.course_id}")

                                if sched.instructor_id:
                                    booked_instr_ranges[(sched.instructor_id, sched.day_id)].append(blocked_range)
                                continue
                    except Exception:
                        pass
                    continue

                s_min, e_min = matched_range
                
                if s_min >= e_min: continue
                
                metadata = {
                    "course_id": sched.course_id,
                    "year": sched.year,
                    "subject_id": sched.subject_id,
                    "description": f"Course {sched.course_id} Year {sched.year}"
                }
                
                # Add to room ranges
                # Use room NAME because cp_scheduler expects names for existing bookings
                if sched.room_id and sched.room:
                    # Provide (room_name, day_id) -> list of (start, end, metadata)
                    key = (sched.room.name, sched.day_id)
                    booked_room_ranges[key].append((s_min, e_min, metadata))
                    
                    # DEBUG: Log if we are blocking any GS ER room
                    if "GS ER" in str(sched.room.name):
                         logger.info(f"[SCHEDULER FILTER MAIN] Blocking {sched.room.name} (ID {sched.room_id}) Day {sched.day_id}: {sched.time} -> {(s_min, e_min)}. SubjID={sched.subject_id}, Year={sched.year}, Course={sched.course_id}")

                
                # Add to instr ranges
                if sched.instructor_id:
                     key = (sched.instructor_id, sched.day_id)
                     booked_instr_ranges[key].append((s_min, e_min, metadata))
            
            logger.info(f"Existing bookings analysis: {regenerating_count} items being replaced, {blocking_count} items treated as blocked.")
            logger.info(f"Constructed {len(booked_room_ranges)} room blocking entries and {len(booked_instr_ranges)} instructor blocking entries.")

            aggregated_results, scheduling_diagnostics = run_cp_scheduler(
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
                booked_room_ranges_global=booked_room_ranges,
                booked_instr_ranges_global=booked_instr_ranges,
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
            
            # DEBUG: Check diagnostics returned from CP
            print(f"DEBUG: run_scheduler received diagnostics from CP. keys={list(scheduling_diagnostics.keys())}")
            if scheduling_diagnostics:
                k = next(iter(scheduling_diagnostics))
                print(f"DEBUG: Sample diag entry [{k}]: {scheduling_diagnostics[k]}")

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
                    if subj is None:
                         continue
                         
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


            return deduped_results, scheduling_diagnostics
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
            return [], {}
        
        instructors = db.query(models.Instructor).filter(
            models.Instructor.is_active == True,
            (models.Instructor.college_id == college_id) | (models.Instructor.college_id.is_(None))
        ).all()
        rooms = db.query(models.Room).filter(models.Room.is_available == True).all()
        days = db.query(models.Day).all()
        
        if not instructors or not rooms or not days:
            return [], {}
        
        logger.info("Using greedy algorithm fallback for %d subjects", len(requested_subject_ids))
        greedy_results = run_greedy_scheduler(
            course_subjects,
            instructors,
            rooms,
            days,
            booked_room_ranges_global=booked_room_ranges,
            booked_instr_ranges_global=booked_instr_ranges,
        )
        
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
        
        return enriched_results, {}
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
        ], {}


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
    
    # ROOM CONFLICT PREVENTION: Track room bookings to prevent double-booking
    # Key: (room_id, day_id, time_str) -> first item that booked this slot
    room_bookings_by_slot = {}  # (room_id, day_id, time) -> schedule_item
    skipped_duplicates = []
    
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
        
        # ROOM CONFLICT CHECK: Prevent double-booking of same room/day/time
        room_id = item.get("room_id")
        if room_id is not None and day_id is not None and time_str:
            room_slot_key = (room_id, day_id, time_str)
            if room_slot_key in room_bookings_by_slot:
                existing_item = room_bookings_by_slot[room_slot_key]
                logger.warning(
                    f"[SAVE CONFLICT] Room double-booking prevented! "
                    f"Room {room_id} Day {day_id} Time {time_str} already assigned to Subject {existing_item.get('subject_id')} Block {existing_item.get('block')}. "
                    f"Skipping Subject {subject_id} Block {block_value}."
                )
                skipped_duplicates.append({
                    "skipped_item": item,
                    "existing_item": existing_item,
                    "reason": "room_double_booking"
                })
                continue
            # Register this room slot as booked
            room_bookings_by_slot[room_slot_key] = item
        
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
    
    # Log summary of skipped duplicates
    if skipped_duplicates:
        logger.warning(f"[SAVE SUMMARY] Skipped {len(skipped_duplicates)} items due to room double-booking conflicts")
    
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

def get_suggestions(
    db: Session,
    subject_id: int,
    course_id: int,
    year: int,
    semester: int,
) -> List[Dict]:
    """Get alternative scheduling suggestions for an unscheduled subject."""
    from .cp_scheduler import find_alternative_slots
    from collections import defaultdict
    from sqlalchemy.orm import joinedload
    from .timeslots import TIME_BLOCKS, time_to_minutes

    # 1. Load Data (Instructors, Rooms, Days)
    # We load broad set then filter? Or just load what we need.
    # We need all rooms and days.
    rooms = db.query(models.Room).filter(models.Room.is_available == True).all()
    days = db.query(models.Day).all()
    
    # College-based room filtering: only use rooms from the subject's college
    subject_obj = db.query(models.Subject).get(subject_id)
    _subj_college_id = None
    if subject_obj and subject_obj.course_id:
        _course = db.query(models.Course).filter(models.Course.id == subject_obj.course_id).first()
        if _course:
            _subj_college_id = _course.college_id
    
    if _subj_college_id is not None:
        _room_college_map = {}
        for _r in rooms:
            if _r.building_id:
                _bldg = db.query(models.Building).get(_r.building_id)
                if _bldg:
                    _room_college_map[_r.id] = getattr(_bldg, 'college_id', None)
        rooms = [
            r for r in rooms
            if _room_college_map.get(r.id) is None or _room_college_map.get(r.id) == _subj_college_id
        ]
    
    # 2. Build Maps
    room_id_to_name = {r.id: r.name for r in rooms}
    
    # 3. Load Existing Bookings (Global)
    # Similar to run_scheduler, we need to know what's booked.
    existing_schedules = db.query(models.Schedule).filter(
        models.Schedule.semester == semester
    ).options(joinedload(models.Schedule.room)).all()

    booked_room_slots_global = set()
    booked_instr_slots_global = set()
    
    # Load slots structure
    from .timeslots import get_slots_by_day
    slots_by_day = get_slots_by_day(days)
    
    # Helper to normalize time strings
    def normalize_time_str(s):
        if not s: return ""
        return s.replace("–", "-").replace("—", "-").replace(" ", "").upper()
        
    # Create lookup for time strings -> range
    block_lookup = {}
    for tb in TIME_BLOCKS:
        norm_label = normalize_time_str(tb['label'])
        start_m = time_to_minutes(tb['start'])
        end_m = time_to_minutes(tb['end'])
        block_lookup[norm_label] = (start_m, end_m)
        
        # 24h
        start_24 = tb['start'].strip()
        end_24 = tb['end'].strip()
        label_24_norm = normalize_time_str(f"{start_24}-{end_24}")
        block_lookup[label_24_norm] = (start_m, end_m)
        if start_24.startswith("0"):
             block_lookup[normalize_time_str(f"{start_24[1:]}-{end_24}")] = (start_m, end_m)

    # Populate booked slots
    for sched in existing_schedules:
        if not sched.time: continue
        
        # Determine range
        matched_range = None
        sched_time_norm = normalize_time_str(sched.time)
        for label_norm, (s_min, e_min) in block_lookup.items():
            if label_norm in sched_time_norm:
                matched_range = (s_min, e_min)
                break
        
        if not matched_range:
             # Try regex fallback
             import re
             times = re.findall(r'(\d{1,2}):(\d{2})', sched.time)
             if len(times) >= 2:
                 h1, m1 = map(int, times[0])
                 h2, m2 = map(int, times[1])
                 def norm_mins(h, m):
                     if h < 7: h += 12
                     elif h == 12: pass 
                     return h * 60 + m
                 s_min = norm_mins(h1, m1)
                 e_min = norm_mins(h2, m2)
                 # simple pm check
                 if "PM" in sched_time_norm and s_min < 720 and h1 < 12: s_min += 720
                 if "PM" in sched_time_norm and e_min < 720 and h2 < 12: e_min += 720
                 matched_range = (s_min, e_min)
        
        if not matched_range: continue
        s_min, e_min = matched_range
        if s_min >= e_min: continue
        
        # Mark occupied slots
        # Map range to day slots
        day_slots = slots_by_day.get(sched.day.label, []) if sched.day else []
        for slot in day_slots:
             # Check overlap
             # slot covers [slot_start, slot_end]
             # sched covers [s_min, e_min]
             slot_s = slot["start_min"]
             slot_e = slot["end_min"]
             # Overlap logic: not (end1 <= start2 or start1 >= end2)
             if not (slot_e <= s_min or slot_s >= e_min):
                 if sched.room_id and sched.room:
                      booked_room_slots_global.add((sched.room.name, sched.day_id, slot["index"]))
                 if sched.instructor_id:
                      booked_instr_slots_global.add((sched.instructor_id, sched.day_id, slot["index"]))

    # 4. Load Eligibility Maps
    # We need to know valid rooms/instructors for this subject
    # Re-use logic from db_procedures or just build complete map for simplicity?
    # Ideally use db_procedures, but let's build map for this specific subject to be fast.
    
    course_to_instructors = defaultdict(list)
    course_to_rooms = defaultdict(list)
    
    # Just fetch for this subject
    from api import db_procedures
    try:
        db_instrs = db_procedures.get_instructor_eligibility(db, subject_id)
        if db_instrs:
            course_to_instructors[subject_id] = [i.id for i in db_instrs]
            
        db_rooms = db_procedures.get_room_eligibility(db, subject_id)
        if db_rooms:
            course_to_rooms[subject_id] = [r.id for r in db_rooms]
    except Exception as e:
        logger.error(f"Error fetching eligibility for suggestion: {e}")

    # 5. Call CP Helper
    return find_alternative_slots(
        db=db,
        subject_id=subject_id,
        course_id=course_id,
        year=year,
        semester=semester,
        rooms=rooms,
        days=days,
        slots_by_day=slots_by_day,
        booked_room_slots_global=booked_room_slots_global,
        booked_instr_slots_global=booked_instr_slots_global,
        course_to_instructors=course_to_instructors,
        course_to_rooms=course_to_rooms,
        room_id_to_name=room_id_to_name
    )

def check_resource_availability(
    db: Session,
    semester: int,
    year: int,
    day_id: int,
    start_min: int,
    end_min: int,
    subject_id: Optional[int] = None
) -> Dict[str, List[int]]:
    """
    Check which rooms and instructors are available during a specific window.
    If subject_id is provided, also filters instructors by subject eligibility.
    """
    from sqlalchemy.orm import joinedload
    from api import db_procedures
    
    # 1. Fetch all resources
    all_rooms = db.query(models.Room).filter(models.Room.is_available == True).all()
    all_instructors = db.query(models.Instructor).filter(models.Instructor.is_active == True).all()
    
    # 2. Identify the requested day label
    day_obj = db.query(models.Day).filter(models.Day.id == day_id).first()
    if not day_obj:
        return {"available_rooms": [r.id for r in all_rooms], "available_instructors": [i.id for i in all_instructors]}
        
    # 3. Fetch existing schedules that might conflict
    # Query schedules for the same semester/year that are on the same day_id
    conflicting_schedules = db.query(models.Schedule).filter(
        models.Schedule.semester == semester,
        models.Schedule.year == year,
        models.Schedule.day_id == day_id
    ).all()
    
    busy_room_ids = set()
    busy_instructor_ids = set()
    
    # 4. Filter for Time Overlap
    import re
    from .timeslots import TIME_BLOCKS, time_to_minutes
    
    def parse_time_range(time_str):
        if not time_str: return None
        # Normalize
        s = time_str.replace("–", "-").replace("—", "-").replace(" ", "").upper()
        
        # Check against TIME_BLOCKS
        for tb in TIME_BLOCKS:
            tb_norm = tb['label'].replace("–", "-").replace("—", "-").replace(" ", "").upper()
            if tb_norm in s:
                 return time_to_minutes(tb['start']), time_to_minutes(tb['end'])
                 
        # Regex fallback
        times = re.findall(r'(\d{1,2}):(\d{2})', s)
        if len(times) >= 2:
             h1, m1 = map(int, times[0])
             h2, m2 = map(int, times[1])
             
             def to_min(h, m):
                 if h < 7: h += 12
                 elif h == 12: pass
                 return h * 60 + m
                 
             s_m = to_min(h1, m1)
             e_m = to_min(h2, m2)
             
             # PM adjust logic simlar to get_suggestions
             if "PM" in s and s_m < 720 and h1 < 12: s_m += 720
             if "PM" in s and e_m < 720 and h2 < 12: e_m += 720
             
             return s_m, e_m
             
        return None

    for sched in conflicting_schedules:
        if not sched.time: continue
        
        rng = parse_time_range(sched.time)
        if not rng: continue
        
        s_exist, e_exist = rng
        
        # Check overlap: request=[start_min, end_min], exist=[s_exist, e_exist]
        # Overlap if NOT (end1 <= start2 or start1 >= end2)
        if not (e_exist <= start_min or s_exist >= end_min):
            # Conflict!
            if sched.room_id:
                busy_room_ids.add(sched.room_id)
            if sched.instructor_id:
                busy_instructor_ids.add(sched.instructor_id)
    
    # 5. Determine base availability (time-based)
    avail_rooms = [r.id for r in all_rooms if r.id not in busy_room_ids]
    avail_instructors = [i.id for i in all_instructors if i.id not in busy_instructor_ids]
    
    # 6. Apply strictly filtering if subject_id is provided
    if subject_id:
        try:
             # Filter Rooms: Shared building logic
             subject = db.query(models.Subject).get(subject_id)
             if subject:
                 subject_code = subject.code.strip().upper() if subject.code else ""
                 is_shared_subj = getattr(subject, 'is_block_shared', False) or subject_code.startswith("NSTP") or subject_code.startswith("PE")
                 # Find rooms in shared buildings
                 shared_room_ids = set()
                 for r in all_rooms:
                     if r.building_id:
                         bldg = db.query(models.Building).get(r.building_id)
                         if bldg and bldg.is_shared:
                             shared_room_ids.add(r.id)
                 
                 if shared_room_ids:
                     if is_shared_subj:
                         # Shared subjects MUST use shared building rooms. Filter out everything else.
                         avail_shared = [rid for rid in avail_rooms if rid in shared_room_ids]
                         if avail_shared:
                             avail_rooms = avail_shared
                         else:
                             avail_rooms = []
                     else:
                         # Non-shared subjects cannot use shared building rooms
                         avail_rooms = [rid for rid in avail_rooms if rid not in shared_room_ids]

             # College-based room filtering: only show rooms from the subject's college
             _subj_college_id = None
             if subject.course_id:
                 _course = db.query(models.Course).filter(models.Course.id == subject.course_id).first()
                 if _course:
                     _subj_college_id = _course.college_id
             
             if _subj_college_id is not None:
                 _room_college_map = {}
                 for _r in all_rooms:
                     if _r.building_id:
                         _bldg = db.query(models.Building).get(_r.building_id)
                         if _bldg:
                             _room_college_map[_r.id] = getattr(_bldg, 'college_id', None)
                 avail_rooms = [
                     rid for rid in avail_rooms
                     if _room_college_map.get(rid) is None or _room_college_map.get(rid) == _subj_college_id
                 ]

             # Filter Instructors: Only show instructors who are BOTH available (time) AND eligible (specialization)
             eligible_instrs = db_procedures.get_instructor_eligibility(db, subject_id)
             
             # Smart Specialization Enforcement:
             # If ANY instructor explicitly lists this subject code in assignable_courses, 
             # restrict the pool to ONLY those specialized instructors.
             # Otherwise, fall back to the broader usage (e.g. College match).
             if subject and eligible_instrs:
                 strict_matches = []
                 subject_code = subject.code.strip().upper()
                 is_shared_subj = getattr(subject, 'is_block_shared', False) or subject_code.startswith("NSTP") or subject_code.startswith("PE")
                 
                 for i in eligible_instrs:
                     if i.assignable_courses:
                         # Split by comma and normalize
                         courses = [c.strip().upper() for c in i.assignable_courses.split(',')]
                         
                         match = False
                         if is_shared_subj:
                             # NSTP/PE special case: match prefix
                             if any(c.startswith("NSTP") or c.startswith("PE") for c in courses):
                                 match = True
                         else:
                             # Exact match for standard subjects
                             if subject_code in courses:
                                 match = True
                                 
                         if match:
                             strict_matches.append(i)
                 
                 # Logic: If we found ANYONE with strict specialization, enforce it.
                 # This prevents "General" instructors from cluttering the list when specialists exist.
                 if strict_matches:
                     eligible_instrs = strict_matches

             if eligible_instrs: # If we have specialized logic, filter.
                  eligible_ids = {i.id for i in eligible_instrs}
                  # Intersect
                  avail_instructors = [i_id for i_id in avail_instructors if i_id in eligible_ids]
                  
                  return {
                      "available_rooms": avail_rooms,
                      "available_instructors": avail_instructors,
                      "eligible_instructors": list(eligible_ids) # Return all eligible, regardless of availability
                  }
        except Exception as e:
             logger.error(f"Error filtering eligible instructors for availability check: {e}")

    return {
        "available_rooms": avail_rooms,
        "available_instructors": avail_instructors,
        "eligible_instructors": [] # No restriction known
    }
