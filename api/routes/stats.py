from flask import Blueprint, jsonify, request
from sqlalchemy import func
from api.db import SessionLocal
from api import models
import logging
import re
from datetime import datetime

stats_bp = Blueprint("stats", __name__)
logger = logging.getLogger(__name__)

def _fmt_course(course):
    """Return a display label for a course, including major when set.
    e.g. BSCS (Network Technology) → 'BSCS (Network Technology)'
         BSIT with no major        → 'BSIT'
    """
    if not course:
        return "—"
    if course.major:
        return f"{course.code} ({course.major})"
    return course.code

def _parse_duration_mins(time_str):
    """Parse a time range string like '7:00 AM - 8:30 AM' and return duration in minutes."""
    if not time_str:
        return 90  # fallback
    try:
        time_str = time_str.replace('\u2013', '-').replace('\u2014', '-')  # normalize dashes
        parts = time_str.split('-')
        if len(parts) < 2:
            return 90
        start_str = parts[0].strip()
        end_str = parts[1].strip()
        # Try 12-hour format
        for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
            try:
                start = datetime.strptime(start_str, fmt)
                end = datetime.strptime(end_str, fmt)
                diff = (end - start).total_seconds() / 60
                return int(diff) if diff > 0 else 90
            except ValueError:
                continue
        return 90
    except Exception:
        return 90

def _get_session():
    return SessionLocal()

@stats_bp.route("/admin", methods=["GET"])
def get_admin_stats():
    """Get basic admin statistics."""
    db = _get_session()
    try:
        semester = request.args.get("semester", default=1, type=int)
        department_id = request.args.get("department_id", default=None, type=int)
        school_year = request.args.get("school_year", default=None, type=str)
        
        # 1. Room Availability / Utilization (slot-based)
        # Instead of raw minutes, count actual scheduled time slots vs max possible.
        # Max possible = max_slots_per_room_per_day × available_weekdays (M-F).
        # SAT/SUN are overflow — not counted in capacity denominator.
        
        all_days = db.query(models.Day).all()
        day_label_map = {d.id: d.label for d in all_days}
        WEEKEND_LABELS = {'SAT', 'SUN', 'S'}
        weekday_ids = {d.id for d in all_days if d.label.upper() not in WEEKEND_LABELS}
        num_weekdays = len(weekday_ids) if weekday_ids else 5
        
        all_rooms = db.query(models.Room).all()
        
        # Fetch schedules (filtered by semester, school_year, department)
        schedules_query = db.query(models.Schedule).filter(models.Schedule.semester == semester)
        if school_year:
            schedules_query = schedules_query.filter(models.Schedule.school_year == school_year)
        if department_id:
            schedules_query = schedules_query.join(models.Course).filter(models.Course.college_id == department_id)
            
        schedules = schedules_query.all()
        
        scheduled_subject_ids = set()
        
        room_slot_count = {}          # room_id -> weekday slots only
        room_weekend_slot_count = {}   # room_id -> weekend slots
        room_day_slots = {}       # room_id -> {day_id -> [time_strings]}
        # Group schedules by (room_id, day_id) for overlap-based conflict detection
        room_day_schedules = {}   # (room_id, day_id) -> [schedule_objs]

        for sched in schedules:
            if sched.subject_id:
                scheduled_subject_ids.add(sched.subject_id)
            
            if sched.room_id:
                # Separate weekday vs weekend slot counts
                if sched.day_id and sched.day_id not in weekday_ids:
                    room_weekend_slot_count[sched.room_id] = room_weekend_slot_count.get(sched.room_id, 0) + 1
                else:
                    room_slot_count[sched.room_id] = room_slot_count.get(sched.room_id, 0) + 1
                if sched.day_id:
                    room_day_slots.setdefault(sched.room_id, {}).setdefault(sched.day_id, []).append(sched.time or '')
            
            # Group for overlap-based conflict detection
            if sched.room_id and sched.day_id and sched.time:
                rd_key = (sched.room_id, sched.day_id)
                room_day_schedules.setdefault(rd_key, []).append(sched)

        # Max slots per room per day based on actual school scheduling rules:
        # Morning: 7:30 AM - 12:00 PM = 3 time blocks (1-1.5 hrs each)
        # Break:   12:00 PM - 1:00 PM (lunch break)
        # Afternoon: 1:00 PM - 7:00 PM = 4 time blocks (1-1.5 hrs each)
        # Total: ~7 usable slots per room per day (using 8 as conservative max)
        MAX_SLOTS_PER_DAY = 8
        
        # Max capacity per room = slots_per_day × weekdays (M-F only)
        MAX_ROOM_SLOTS = MAX_SLOTS_PER_DAY * num_weekdays

        conflict_details = []
        conflict_count = 0
        total_conflicting_items = 0

        # Pre-build a lookup: room_id -> is_shared_building
        # Shared buildings (GYM, FIELD, COURT, etc.) can legitimately host
        # multiple sections of NSTP / PE / PATHFIT at the same time.
        room_shared_cache = {}
        for r in all_rooms:
            is_shared = False
            if r.building:
                is_shared = bool(r.building.is_shared)
            room_shared_cache[r.id] = is_shared

        # Helper: check if a schedule item is a "shared-venue" subject
        # (NSTP, PE, PATHFIT, or any subject flagged as block-shared)
        def _is_shared_venue_subject(sched_item):
            subj = sched_item.subject
            if not subj:
                return False
            if subj.is_block_shared:
                return True
            code_upper = (subj.code or "").strip().upper()
            return (code_upper.startswith("NSTP")
                    or code_upper.startswith("PE ")
                    or code_upper.startswith("PE-")
                    or code_upper.startswith("PE.")
                    or code_upper == "PE"
                    or code_upper.startswith("PATHFIT"))

        # Helper: parse a time string like "10:30 AM - 11:30 AM" or "5:30 PM - 7:00 PM"
        import re as _re
        def _parse_time_range(time_str):
            if not time_str:
                return None, None
            normalized = time_str.replace("\u2013", "-").replace("\u2014", "-")
            # Match HH:MM with optional AM/PM marker
            matches = _re.findall(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', normalized, _re.IGNORECASE)
            if len(matches) >= 2:
                h1, m1, ampm1 = int(matches[0][0]), int(matches[0][1]), (matches[0][2] or '').upper()
                h2, m2, ampm2 = int(matches[1][0]), int(matches[1][1]), (matches[1][2] or '').upper()
                # Convert to 24-hour using AM/PM markers first, heuristic as fallback
                if ampm1 == 'PM' and h1 < 12:
                    h1 += 12
                elif ampm1 == 'AM' and h1 == 12:
                    h1 = 0
                elif not ampm1 and h1 < 7:
                    h1 += 12
                if ampm2 == 'PM' and h2 < 12:
                    h2 += 12
                elif ampm2 == 'AM' and h2 == 12:
                    h2 = 0
                elif not ampm2 and h2 < 7:
                    h2 += 12
                return h1 * 60 + m1, h2 * 60 + m2
            return None, None

        # Detect overlapping schedules in the same room and day
        for (room_id, day_id), items in room_day_schedules.items():
            if len(items) < 2:
                continue

            is_shared_room = room_shared_cache.get(room_id, False)

            # Parse time ranges for all items
            parsed_items = []
            for item in items:
                start_min, end_min = _parse_time_range(item.time)
                if start_min is not None and end_min is not None and start_min < end_min:
                    parsed_items.append((item, start_min, end_min))

            if len(parsed_items) < 2:
                continue

            # Find overlapping clusters using union-find approach:
            # Two items overlap if max(start1, start2) < min(end1, end2)
            n = len(parsed_items)
            in_conflict = [False] * n
            for i in range(n):
                for j in range(i + 1, n):
                    s1, e1 = parsed_items[i][1], parsed_items[i][2]
                    s2, e2 = parsed_items[j][1], parsed_items[j][2]
                    if max(s1, s2) < min(e1, e2):
                        in_conflict[i] = True
                        in_conflict[j] = True

            conflicting_items = [parsed_items[i][0] for i in range(n) if in_conflict[i]]

            if len(conflicting_items) < 2:
                continue

            # If the room is in a shared building AND every conflicting
            # item is a shared-venue subject (NSTP, PE, PATHFIT, etc.),
            # this is expected — not a real conflict.
            if is_shared_room and all(_is_shared_venue_subject(it) for it in conflicting_items):
                continue

            conflict_count += 1
            total_conflicting_items += len(conflicting_items)
            
            # Format for frontend — show the time range that spans all overlapping items
            all_starts = [parsed_items[i][1] for i in range(n) if in_conflict[i]]
            all_ends = [parsed_items[i][2] for i in range(n) if in_conflict[i]]
            earliest = min(all_starts)
            latest = max(all_ends)
            time_display = f"{earliest // 60}:{earliest % 60:02d}-{latest // 60}:{latest % 60:02d}"

            room_obj = conflicting_items[0].room
            day_obj = conflicting_items[0].day
            
            conflict_group = {
                "room": room_obj.name if room_obj else f"Room {room_id}",
                "day": day_obj.label if day_obj else f"Day {day_id}",
                "time": time_display,
                "items": [],
                "is_shared_room": is_shared_room,
            }
            
            for item in conflicting_items:
                subj = item.subject
                conflict_group["items"].append({
                    "id": item.id,
                    "subject_code": subj.code if subj else "Unknown",
                    "description": subj.description if subj else "",
                    "instructor": f"{item.instructor.first_name} {item.instructor.last_name}" if item.instructor else "TBA",
                    "is_shared_subject": _is_shared_venue_subject(item),
                    "time": item.time,
                    "course": _fmt_course(item.course),
                })
            
            conflict_details.append(conflict_group)

        # Filter rooms by department: show rooms used by the department's schedules
        # plus rooms in buildings that belong to the department
        if department_id:
            dept_room_ids = set(room_slot_count.keys())  # rooms used in dept schedules
            # Also include rooms in buildings owned by this department
            dept_buildings = db.query(models.Building.id).filter(
                models.Building.college_id == department_id
            ).all()
            dept_building_ids = {b[0] for b in dept_buildings}
            for r in all_rooms:
                if r.building_id and r.building_id in dept_building_ids:
                    dept_room_ids.add(r.id)
            rooms = [r for r in all_rooms if r.id in dept_room_ids]
        else:
            rooms = all_rooms

        total_rooms = len(rooms)

        # Room Stats (slot-based, weekday only for utilization)
        active_rooms = sum(1 for r in rooms if room_slot_count.get(r.id, 0) > 0 or room_weekend_slot_count.get(r.id, 0) > 0)
        avg_utilization = 0
        if rooms and MAX_ROOM_SLOTS > 0:
            total_used_slots = sum(room_slot_count.get(r.id, 0) for r in rooms)  # weekday only
            total_capacity_slots = total_rooms * MAX_ROOM_SLOTS
            avg_utilization = (total_used_slots / total_capacity_slots) * 100 if total_capacity_slots > 0 else 0
            avg_utilization = min(avg_utilization, 100.0)  # cap at 100%

        # Per-room detail list
        room_details = []
        for r in rooms:
            weekday_slots = room_slot_count.get(r.id, 0)
            weekend_slots = room_weekend_slot_count.get(r.id, 0)
            total_slots = weekday_slots + weekend_slots
            pct = round((weekday_slots / MAX_ROOM_SLOTS) * 100, 1) if MAX_ROOM_SLOTS > 0 else 0
            # Cap at 100% — weekend overflow is shown separately
            pct = min(pct, 100.0)
            building_name = r.building.name if r.building else None
            room_details.append({
                "id": r.id,
                "name": r.name,
                "type": r.type,
                "building": building_name,
                "capacity": r.capacity or 0,
                "scheduled_slots": total_slots,
                "weekday_slots": weekday_slots,
                "weekend_slots": weekend_slots,
                "max_slots": MAX_ROOM_SLOTS,
                "utilization_pct": pct,
            })
        room_details.sort(key=lambda x: x["utilization_pct"], reverse=True)

        # 2. Instructor Availability / Load
        instructors_query = db.query(models.Instructor).filter(models.Instructor.is_active == True)
        if department_id:
            instructors_query = instructors_query.filter(models.Instructor.college_id == department_id)
            
        instructors = instructors_query.all()
        total_instructors = len(instructors)
        dept_instructor_ids = {i.id for i in instructors}
        
        active_instructor_ids = set(s.instructor_id for s in schedules if s.instructor_id)
        # Only count instructors that belong to this department's roster
        active_instructors = len(active_instructor_ids & dept_instructor_ids) if department_id else len(active_instructor_ids)

        # Per-instructor detail list with load info
        instructor_details = []
        # Pre-compute units loaded per instructor from current schedules
        # Count distinct (subject_id, block) pairs per instructor — each unique class counts once
        instr_subject_block_map = {}  # instr_id -> set of (subject_id, block)
        for sched in schedules:
            if sched.instructor_id and sched.subject_id:
                block = getattr(sched, 'block', None) or ''
                instr_subject_block_map.setdefault(sched.instructor_id, set()).add((sched.subject_id, block))

        # Pre-load subject unit map
        all_subject_ids = set()
        for pairs in instr_subject_block_map.values():
            for sid, _ in pairs:
                all_subject_ids.add(sid)
        subject_units = {}
        if all_subject_ids:
            for s in db.query(models.Subject).filter(models.Subject.id.in_(all_subject_ids)).all():
                subject_units[s.id] = s.unit or 0

        for instr in instructors:
            _, regular_cap = _load_caps()
            max_u = instr.max_units or regular_cap
            # Sum units of distinct (subject, block) pairs assigned
            loaded_units = 0
            assigned_pairs = instr_subject_block_map.get(instr.id, set())
            for sid, _ in assigned_pairs:
                loaded_units += subject_units.get(sid, 0)

            pct = round((loaded_units / max_u) * 100, 1) if max_u > 0 else 0
            if loaded_units > max_u:
                status = "overloaded"
            elif pct >= 80:
                status = "near_capacity"
            elif loaded_units > 0:
                status = "active"
            else:
                status = "available"

            slot_count = sum(1 for s in schedules if s.instructor_id == instr.id)

            # Count unique subjects (not subject-block pairs) for the subject_count display
            unique_subjects = set(sid for sid, _ in assigned_pairs)

            college_name = instr.college.code if instr.college else None
            home_course = instr.home_course
            instructor_details.append({
                "id": instr.id,
                "name": f"{instr.last_name}, {instr.first_name}",
                "college": college_name,
                "home_program": _fmt_course(home_course) if home_course else None,
                "employment_type": instr.employment_type or "N/A",
                "loaded_units": loaded_units,
                "max_units": max_u,
                "load_pct": pct,
                "status": status,
                "scheduled_slots": slot_count,
                "subject_count": len(unique_subjects),
            })
        instructor_details.sort(key=lambda x: x["load_pct"], reverse=True)
        
        # 3. Unscheduled Subjects
        subjects_total_query = db.query(models.Subject).filter(models.Subject.semester == semester)
        if department_id:
            subjects_total_query = subjects_total_query.join(models.Course).filter(models.Course.college_id == department_id)
            
        total_subjects = subjects_total_query.count()
        unscheduled_count = total_subjects - len(scheduled_subject_ids)
        if unscheduled_count < 0: unscheduled_count = 0 

        # Fetch a few unscheduled for display
        unscheduled_sample = []
        if unscheduled_count > 0:
             unscheduled_query = db.query(models.Subject).filter(
                 models.Subject.semester == semester,
                 models.Subject.id.notin_(scheduled_subject_ids)
             )
             if department_id:
                 unscheduled_query = unscheduled_query.join(models.Course).filter(models.Course.college_id == department_id)
             
             unscheduled_objs = unscheduled_query.limit(5).all()
             unscheduled_sample = [{
                 "code": s.code,
                 "description": s.description,
                 "course": _fmt_course(s.course),
                 "year_level": s.year_level or "—",
                 "semester": s.semester or "—",
                 "type": s.type or "—",
             } for s in unscheduled_objs]

        # 4. Recommendations
        recommendations = []
        overloaded_count = sum(1 for i in instructor_details if i["status"] == "overloaded")
        near_cap_count = sum(1 for i in instructor_details if i["status"] == "near_capacity")
        if avg_utilization > 80:
             recommendations.append("High room utilization detected. Consider adding more rooms or extending hours.")
        if conflict_count > 0:
             recommendations.append(f"Found {conflict_count} schedule conflicts. Please resolve them using the conflict resolution tool.")
        if unscheduled_count > 0:
             recommendations.append(f"{unscheduled_count} subjects are unscheduled. Use the Schedule Generator to assign them.")
        if overloaded_count > 0:
             recommendations.append(f"{overloaded_count} instructor(s) are overloaded beyond their max units. Review their assignments.")
        if near_cap_count > 0:
             recommendations.append(f"{near_cap_count} instructor(s) are near capacity (≥80% load). Monitor before assigning more.")
        
        if not recommendations:
             recommendations.append("System is running smoothly. No critical issues detected.")

        return jsonify({
            "rooms": {
                "total": total_rooms,
                "active": active_rooms,
                "utilization_pct": round(avg_utilization, 1),
                "details": room_details
            },
            "instructors": {
                "total": total_instructors,
                "active": active_instructors,
                "utilization_pct": min(round((active_instructors/total_instructors)*100, 1), 100.0) if total_instructors else 0,
                "overloaded": overloaded_count,
                "near_capacity": near_cap_count,
                "details": instructor_details
            },
            "conflicts": {
                "count": conflict_count,
                "affected_items": total_conflicting_items,
                "details": conflict_details
            },
            "subjects": {
                "total": total_subjects,
                "scheduled": len(scheduled_subject_ids),
                "unscheduled": unscheduled_count,
                "sample_unscheduled": unscheduled_sample
            },
            "recommendations": recommendations
        })

    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}", exc_info=True)
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()


@stats_bp.route("/room-utilization-by-day", methods=["GET"])
def get_room_utilization_by_day():
    """Return global per-room-type per-day slot utilization.

    Used by the Registrar page to show accurate slot-based utilization
    matching the Admin Dashboard numbers (8 slots/day, weekday-only capacity).
    """
    db = _get_session()
    try:
        semester = request.args.get("semester", default=1, type=int)
        school_year = request.args.get("school_year", default=None, type=str)
        course_id = request.args.get("course_id", default=None, type=int)

        all_days = db.query(models.Day).all()
        WEEKEND_LABELS = {'SAT', 'SUN', 'S'}

        # If course_id is given, find its college to filter eligible rooms
        course_college_id = None
        if course_id:
            course = db.query(models.Course).filter(models.Course.id == course_id).first()
            if course:
                course_college_id = course.college_id

        # Build building lookup for college-based room filtering
        bldg_college_map = {}  # building_id -> college_id
        bldg_shared_map = {}   # building_id -> is_shared
        for b in db.query(models.Building).all():
            bldg_college_map[b.id] = b.college_id
            bldg_shared_map[b.id] = b.is_shared

        all_rooms = db.query(models.Room).all()
        room_type_map = {}       # room_id -> type
        available_rooms_of_type = {}  # type -> set of room_ids (available only)
        for r in all_rooms:
            t = (r.type or 'LEC').upper()
            room_type_map[r.id] = t
            if r.is_available:
                # If course filtering is active, only include rooms from the
                # same college, shared buildings, or rooms with no building
                if course_college_id:
                    b_col = bldg_college_map.get(r.building_id)
                    b_shared = bldg_shared_map.get(r.building_id, False)
                    if not (b_col == course_college_id or b_shared or not r.building_id):
                        continue
                available_rooms_of_type.setdefault(t, set()).add(r.id)

        # Fetch ALL schedules for the semester (global, not course-filtered)
        sched_q = db.query(models.Schedule).filter(models.Schedule.semester == semester)
        if school_year:
            sched_q = sched_q.filter(models.Schedule.school_year == school_year)
        schedules = sched_q.all()

        # Parse time ranges for each schedule item and group by (room_id, day_id)
        import re as _re
        from api.scheduler.timeslots import TIME_BLOCKS, time_to_minutes

        def _parse_time(time_str):
            if not time_str:
                return None, None
            normalized = time_str.replace("\u2013", "-").replace("\u2014", "-")
            # Match HH:MM with optional AM/PM marker
            matches = _re.findall(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', normalized, _re.IGNORECASE)
            if len(matches) >= 2:
                h1, m1, ampm1 = int(matches[0][0]), int(matches[0][1]), (matches[0][2] or '').upper()
                h2, m2, ampm2 = int(matches[1][0]), int(matches[1][1]), (matches[1][2] or '').upper()
                # Convert to 24-hour using AM/PM markers first, heuristic as fallback
                if ampm1 == 'PM' and h1 < 12:
                    h1 += 12
                elif ampm1 == 'AM' and h1 == 12:
                    h1 = 0
                elif not ampm1 and h1 < 7:
                    h1 += 12
                if ampm2 == 'PM' and h2 < 12:
                    h2 += 12
                elif ampm2 == 'AM' and h2 == 12:
                    h2 = 0
                elif not ampm2 and h2 < 7:
                    h2 += 12
                return h1 * 60 + m1, h2 * 60 + m2
            return None, None

        # Build per-room per-day booked time ranges
        room_day_ranges = {}  # (room_id, day_id) -> [(start_min, end_min), ...]
        type_day_rooms = {}   # (type, day_id) -> set of room_ids

        for sched in schedules:
            if not sched.room_id or not sched.day_id:
                continue
            s_min, e_min = _parse_time(sched.time)
            if s_min is None or e_min is None or s_min >= e_min:
                continue
            rd_key = (sched.room_id, sched.day_id)
            room_day_ranges.setdefault(rd_key, []).append((s_min, e_min))
            rtype = room_type_map.get(sched.room_id, 'LEC')
            td_key = (rtype, sched.day_id)
            type_day_rooms.setdefault(td_key, set()).add(sched.room_id)

        # Pre-compute TIME_BLOCK ranges for overlap checking
        # Exclude NSTP Sunday block (8:00-11:00)
        tb_ranges = []
        for tb in TIME_BLOCKS:
            s = time_to_minutes(tb["start"])
            e = time_to_minutes(tb["end"])
            if e - s >= 180:  # Skip 3-hour NSTP block
                continue
            tb_ranges.append((s, e))

        def _count_available_slots(room_id, day_id):
            """Count how many TIME_BLOCKS have NO overlap with existing bookings."""
            booked = room_day_ranges.get((room_id, day_id), [])
            available = 0
            for tb_s, tb_e in tb_ranges:
                is_free = True
                for b_s, b_e in booked:
                    if not (tb_e <= b_s or b_e <= tb_s):  # overlap
                        is_free = False
                        break
                if is_free:
                    available += 1
            return available

        TOTAL_SLOTS_PER_ROOM = len(tb_ranges)  # e.g. 13 schedulable blocks

        # Find which rooms of each type are actively used globally (any day)
        rooms_with_schedules = {}  # type -> set of room_ids that have at least 1 slot
        for sched in schedules:
            if sched.room_id:
                rtype = room_type_map.get(sched.room_id, 'LEC')
                rooms_with_schedules.setdefault(rtype, set()).add(sched.room_id)

        # Build room name lookup
        room_name_map = {r.id: r.name for r in all_rooms}

        result = []
        for rtype, room_ids in available_rooms_of_type.items():
            type_label = 'Laboratory' if rtype == 'LAB' else 'Lecture'
            total_room_count = len(room_ids)

            # Active rooms = available rooms that have at least 1 scheduled slot
            active_ids = room_ids & rooms_with_schedules.get(rtype, set())
            active_count = len(active_ids)
            unused_ids = room_ids - active_ids
            unused_rooms = sorted([room_name_map.get(rid, f"Room {rid}") for rid in unused_ids])

            # Max slots capacity for active rooms
            max_slots_active = active_count * TOTAL_SLOTS_PER_ROOM

            for day in all_days:
                if not day.id:
                    continue
                day_label = day.label or ''
                is_weekend = day_label.upper() in WEEKEND_LABELS
                td_key = (rtype, day.id)
                rooms_used = len(type_day_rooms.get(td_key, set()))

                # Count total available slots across all active rooms on this day
                total_available = 0
                for rid in active_ids:
                    total_available += _count_available_slots(rid, day.id)

                slots_used = max_slots_active - total_available

                # Percentage = how full are the rooms (occupied/total)
                pct = round((slots_used / max_slots_active) * 100) if max_slots_active > 0 else 0

                result.append({
                    "type": rtype,
                    "typeLabel": type_label,
                    "day": day_label,
                    "dayId": day.id,
                    "isWeekend": is_weekend,
                    "slotsUsed": slots_used,
                    "maxSlots": max_slots_active,
                    "maxSlotsTotal": total_room_count * TOTAL_SLOTS_PER_ROOM,
                    "slotsAvailable": total_available,
                    "roomsUsed": rooms_used,
                    "activeRooms": active_count,
                    "totalRooms": total_room_count,
                    "unusedRooms": unused_rooms,
                    "percentage": pct,
                })

        # Sort by canonical day order: M, T, W, TH, F, SAT, SUN
        _DAY_ORDER = {'M': 1, 'T': 2, 'W': 3, 'TH': 4, 'F': 5, 'SAT': 6, 'SUN': 7, 'S': 6}
        result.sort(key=lambda x: (_DAY_ORDER.get(x['day'].upper(), 99), x['type']))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching room utilization by day: {e}", exc_info=True)
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()


# ── Designation-based unit caps (CHED/DBM guidelines) ───────────────
DESIGNATION_CAPS = {
    "dean":              9,
    "associate dean":   12,
    "program chair":    15,
    "director":          9,
    "college secretary": 12,
}

def _load_caps():
    """Load base hour limits from system_settings."""
    try:
        from ..scheduler.settings import get_system_settings
        s = get_system_settings()
        return int(s.get("visiting_base_hours", 30)), int(s.get("regular_base_hours", 24))
    except Exception:
        return 30, 24

MAX_LEC_SECTIONS = 3   # time-slot limit per prof for same LEC subject
MAX_LAB_SECTIONS = 4   # time-slot limit per prof for same LAB subject


def _instructor_unit_cap(instructor):
    """Return the teaching-unit cap for an instructor based on designation."""
    if instructor.max_units:
        return instructor.max_units
    visiting_cap, regular_cap = _load_caps()
    emp = (instructor.employment_type or "regular").strip().lower()
    if emp == "visiting":
        return visiting_cap
    desg = (instructor.designation or "").strip().lower()
    return DESIGNATION_CAPS.get(desg, regular_cap)


def _normalize_code(code):
    """Normalise a subject code for matching.
    Strips all non-alphanumeric chars, then collapses known abbreviation
    variants so that 'Prof.E 7' (PROFE7) and 'ProE 7' (PROE7) match.
    """
    import re
    base = re.sub(r'[^A-Z0-9]', '', (code or '').upper())
    # Collapse Professional Elective abbreviation variants
    base = re.sub(r'PROFE(?=\d)', 'PROE', base)
    base = re.sub(r'CSPROFELECT', 'CSPROE', base)
    return base


@stats_bp.route("/staffing", methods=["GET"])
def get_staffing_analysis():
    """Compute per-subject professor requirements with effective-capacity model."""
    db = _get_session()
    try:
        semester      = request.args.get("semester", default=1, type=int)
        blocks        = request.args.get("blocks",   default=3, type=int)
        department_id = request.args.get("department_id", default=None, type=int)
        school_year   = request.args.get("school_year",   default=None, type=str)

        blocks = max(1, min(blocks, 4))

        # ── 1. Load subjects for this semester ──────────────────────
        subj_q = db.query(models.Subject).filter(models.Subject.semester == semester)
        if department_id:
            subj_q = subj_q.join(models.Course).filter(models.Course.college_id == department_id)
        all_subjects = subj_q.all()

        # Group by normalised (code, description, type) — same code can have
        # different subjects (e.g. IT 104 "Social and Professional Issues" LEC 3u
        # vs IT 104 "Networking 1" LEC 2u)
        subj_groups = {}   # key -> {codes, units, shared, is_major, courses, subj_ids}
        for s in all_subjects:
            desc_norm = (s.description or "").strip().lower()
            key = (_normalize_code(s.code), desc_norm, s.type)
            if key not in subj_groups:
                subj_groups[key] = {
                    "code": s.code.strip(), "type": s.type, "units": s.unit or 0,
                    "description": (s.description or "").strip(),
                    "shared": s.is_block_shared, "is_major": s.is_major,
                    "courses": set(), "subj_ids": set(), "year_levels": set(),
                }
            sg = subj_groups[key]
            if s.course:
                sg["courses"].add(_fmt_course(s.course))
            sg["subj_ids"].add(s.id)
            if s.year_level:
                sg["year_levels"].add(s.year_level)

        # ── 2. Load active instructors & parse assignable subjects ──
        instr_q = db.query(models.Instructor).filter(models.Instructor.is_active == True)
        if department_id:
            instr_q = instr_q.filter(models.Instructor.college_id == department_id)
        instructors = instr_q.all()

        # Build instructor → set-of-normalised-codes
        instr_subjects_map = {}   # instr.id → set of normalised codes
        for inst in instructors:
            raw = inst.assignable_courses or ""
            codes = {_normalize_code(c) for c in raw.split(",") if c.strip()}
            instr_subjects_map[inst.id] = codes

        # ── 3. Compute current scheduled load per instructor ────────
        sched_q = db.query(models.Schedule).filter(models.Schedule.semester == semester)
        if school_year:
            sched_q = sched_q.filter(models.Schedule.school_year == school_year)
        else:
            # Auto-detect latest school year
            latest_sy = (
                db.query(func.max(models.Schedule.school_year))
                .filter(models.Schedule.semester == semester)
                .scalar()
            )
            if latest_sy:
                sched_q = sched_q.filter(models.Schedule.school_year == latest_sy)
            school_year = latest_sy or "N/A"

        schedules = sched_q.all()

        # Units loaded per instructor (unique subject-block combos)
        instr_loaded = {}   # instr_id → total units
        subj_unit_map = {s.id: (s.unit or 0) for s in all_subjects}
        # Also load any subject IDs from schedules not yet in the map
        extra_ids = {sc.subject_id for sc in schedules if sc.subject_id and sc.subject_id not in subj_unit_map}
        if extra_ids:
            for es in db.query(models.Subject).filter(models.Subject.id.in_(extra_ids)).all():
                subj_unit_map[es.id] = es.unit or 0

        seen_pairs = set()
        for sc in schedules:
            if sc.instructor_id and sc.subject_id:
                pair = (sc.instructor_id, sc.subject_id, sc.block or "")
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    instr_loaded[sc.instructor_id] = instr_loaded.get(sc.instructor_id, 0) + subj_unit_map.get(sc.subject_id, 0)

        # ── Cross-semester subject lookup for S1/S2 balance ────────
        other_sem = 2 if semester == 1 else 1
        other_subjects = db.query(models.Subject).filter(
            models.Subject.semester == other_sem
        ).all()
        other_subj_norms = set()
        for s in other_subjects:
            other_subj_norms.add(_normalize_code(s.code))

        current_subj_norms = set()
        for sg in subj_groups.values():
            current_subj_norms.add(_normalize_code(sg["code"]))

        def _instructor_sem_balance(inst_codes):
            """Return S1/S2 subject lists for a set of instructor codes."""
            s1_list, s2_list, both_list = [], [], []
            for code in sorted(inst_codes):
                in_cur = code in current_subj_norms
                in_oth = code in other_subj_norms
                if in_cur and in_oth:
                    both_list.append(code)
                elif in_cur:
                    (s1_list if semester == 1 else s2_list).append(code)
                elif in_oth:
                    (s2_list if semester == 1 else s1_list).append(code)
            return s1_list, s2_list, both_list

        # ── 4. For each subject group, compute effective professors ─
        results = []

        for key, sg in sorted(subj_groups.items(), key=lambda x: (-len(x[1]["courses"]), x[0][0])):
            code_norm = _normalize_code(sg["code"])
            num_courses = len(sg["courses"])
            units = sg["units"]

            # Sections needed
            if sg["shared"]:
                total_sections = num_courses or 1
            else:
                total_sections = max(num_courses, 1) * blocks

            # Professors needed (each can handle ~3 LEC or ~4 LAB sections)
            max_sec = MAX_LAB_SECTIONS if sg["type"] == "LAB" else MAX_LEC_SECTIONS
            profs_needed = max(
                (total_sections + max_sec - 1) // max_sec,    # ceiling division
                num_courses if not sg["shared"] else 1,        # concurrency minimum
            )

            # Find matching instructors
            matching = []
            for inst in instructors:
                if code_norm in instr_subjects_map.get(inst.id, set()):
                    matching.append(inst)

            raw_profs = len(matching)

            # Compute effective contribution per instructor
            effective_total = 0.0
            instr_details = []

            for inst in matching:
                cap = _instructor_unit_cap(inst)
                loaded = instr_loaded.get(inst.id, 0)
                remaining = max(0, cap - loaded)
                emp_type = (inst.employment_type or "regular").strip().lower()
                desg = (inst.designation or "").strip()

                # Count competing subjects in THIS semester that also need this instructor
                # Count by unique CODE (not by group), since LEC/LAB of the same subject
                # and same-code entries with different descriptions are ONE teaching assignment
                current_norm_code = _normalize_code(sg["code"])
                competing_codes = set()
                for other_key, other_sg in subj_groups.items():
                    if other_key == key:
                        continue
                    other_norm = _normalize_code(other_sg["code"])
                    if other_norm == current_norm_code:
                        continue  # Same code as current subject doesn't count
                    if other_norm in instr_subjects_map.get(inst.id, set()):
                        competing_codes.add(other_norm)
                competing = len(competing_codes)

                # Fair share of remaining capacity for this subject
                divisor = competing + 1
                fair_share = remaining / divisor if divisor > 0 else remaining

                # How many sections of this subject can this prof handle?
                sections_can_handle = min(
                    max_sec,
                    int(fair_share // units) if units > 0 else 0,
                )

                # Effective contribution as a fraction of "one full professor"
                # 1.0 means they can handle their full share (3 LEC / 4 LAB sections)
                contribution = min(1.0, sections_can_handle / max_sec) if max_sec > 0 else 0.0
                effective_total += contribution

                # Determine status
                if remaining <= 0:
                    status = "at_capacity"
                elif desg and desg.lower() in DESIGNATION_CAPS:
                    status = "limited_by_designation"
                elif competing >= 6:
                    status = "spread_thin"
                else:
                    status = "available"

                instr_codes = instr_subjects_map.get(inst.id, set())
                s1_list, s2_list, both_list = _instructor_sem_balance(instr_codes)

                instr_details.append({
                    "id": inst.id,
                    "name": f"{inst.first_name} {inst.last_name}",
                    "type": emp_type,
                    "designation": desg or None,
                    "unit_cap": cap,
                    "current_load": loaded,
                    "remaining": remaining,
                    "competing_subjects": competing,
                    "fair_share_units": round(fair_share, 1),
                    "sections_can_handle": sections_can_handle,
                    "effective_contribution": round(contribution, 2),
                    "status": status,
                    "s1_count": len(s1_list) + len(both_list),
                    "s2_count": len(s2_list) + len(both_list),
                    "s1_subjects": s1_list,
                    "s2_subjects": s2_list,
                    "both_subjects": both_list,
                    "total_specialties": len(instr_codes),
                })

            # Sort instructors: best contributors first
            instr_details.sort(key=lambda x: -x["effective_contribution"])

            gap_raw = profs_needed - raw_profs
            gap_eff = round(profs_needed - effective_total, 1)

            if gap_eff >= 2:
                severity = "critical"
            elif gap_eff >= 1:
                severity = "warning"
            else:
                severity = "ok"

            results.append({
                "code": sg["code"],
                "description": sg.get("description", ""),
                "type": sg["type"],
                "units": units,
                "is_major": sg["is_major"],
                "shared": sg["shared"],
                "courses": sorted(sg["courses"]),
                "year_levels": sorted(sg["year_levels"]),
                "sections_needed": total_sections,
                "profs_needed": profs_needed,
                "raw_profs": raw_profs,
                "effective_profs": round(effective_total, 1),
                "gap_raw": gap_raw,
                "gap_effective": gap_eff,
                "severity": severity,
                "instructors": instr_details,
            })

        # ── 5. Instructor-level warnings with semester balance ──────
        # (cross-semester norms already computed above)
        instr_warnings = []
        for inst in instructors:
            cap = _instructor_unit_cap(inst)
            codes = instr_subjects_map.get(inst.id, set())
            loaded = instr_loaded.get(inst.id, 0)
            name = f"{inst.first_name} {inst.last_name}"
            emp = (inst.employment_type or "regular").strip().lower()
            desg = (inst.designation or "").strip()

            # Count how many unique subject codes this semester match this instructor
            # (count unique codes, not individual groups — LEC/LAB and duplicate
            # descriptions of the same code are one teaching assignment)
            sem_matched_codes = set()
            for k in subj_groups:
                norm = _normalize_code(subj_groups[k]["code"])
                if norm in codes:
                    sem_matched_codes.add(norm)
            sem_count = len(sem_matched_codes)
            coverable = max(1, int(cap / 3)) if cap > 0 else 0

            # Semester balance: which of their specialties are in S1, S2, or both?
            s1_list = []
            s2_list = []
            both_list = []
            unmatched_list = []
            for code in sorted(codes):
                in_current = code in current_subj_norms
                in_other = code in other_subj_norms
                if in_current and in_other:
                    both_list.append(code)
                elif in_current:
                    s1_list.append(code) if semester == 1 else s2_list.append(code)
                elif in_other:
                    s2_list.append(code) if semester == 1 else s1_list.append(code)
                else:
                    unmatched_list.append(code)

            this_sem_count = len(s1_list if semester == 1 else s2_list) + len(both_list)
            other_sem_count = len(s2_list if semester == 1 else s1_list) + len(both_list)

            base_info = {
                "id": inst.id, "name": name,
                "employment_type": emp,
                "designation": desg or None,
                "unit_cap": cap,
                "current_load": loaded,
                "total_specialties": len(codes),
                "s1_count": len(s1_list) + len(both_list),
                "s2_count": len(s2_list) + len(both_list),
                "s1_subjects": s1_list,
                "s2_subjects": s2_list,
                "both_subjects": both_list,
                "unmatched": unmatched_list,
                "this_semester_count": this_sem_count,
                "other_semester_count": other_sem_count,
            }

            # Determine issues
            issues = []

            if len(codes) <= 1 and not desg and emp != "visiting":
                issues.append({
                    **base_info,
                    "issue": "underspecialized",
                    "detail": f"Has only {len(codes)} assignable subject(s). Consider adding more specializations for scheduling flexibility.",
                })
            elif sem_count > coverable and not desg:
                issues.append({
                    **base_info,
                    "issue": "overspecialized",
                    "detail": f"Has {sem_count} subjects this semester but can realistically cover ~{coverable} with {cap}-unit cap.",
                    "subjects_coverable": coverable,
                })

            if loaded > cap:
                issues.append({
                    **base_info,
                    "issue": "overloaded",
                    "detail": f"Currently loaded {loaded} units, exceeding {cap}-unit cap by {loaded - cap} units.",
                })

            # Semester imbalance flags
            if this_sem_count > 0 and other_sem_count == 0 and len(codes) > 1:
                sem_label = f"S{semester}"
                other_label = f"S{other_sem}"
                issues.append({
                    **base_info,
                    "issue": "semester_lopsided",
                    "detail": f"All {this_sem_count} subjects are in {sem_label}, zero in {other_label}. Idle during {other_label}. Consider adding {other_label} subjects.",
                })
            elif this_sem_count == 0 and other_sem_count > 0 and len(codes) > 1:
                sem_label = f"S{semester}"
                other_label = f"S{other_sem}"
                issues.append({
                    **base_info,
                    "issue": "no_subjects_this_sem",
                    "detail": f"Has {other_sem_count} subjects in {other_label} but nothing in {sem_label}. Completely idle this semester.",
                })
            elif this_sem_count <= 1 and other_sem_count >= 4 and len(codes) > 2:
                sem_label = f"S{semester}"
                other_label = f"S{other_sem}"
                issues.append({
                    **base_info,
                    "issue": "semester_heavy",
                    "detail": f"Only {this_sem_count} subject(s) in {sem_label} vs {other_sem_count} in {other_label}. Consider moving some specialties to balance.",
                })

            if not issues:
                # Still add to the list so the UI can show all instructors with their S1/S2 split
                issues.append({
                    **base_info,
                    "issue": "balanced",
                    "detail": f"{this_sem_count} subjects this semester, {other_sem_count} other semester.",
                })

            instr_warnings.extend(issues)

        # ── 6. Auto-generate recommendations ────────────────────────
        recommendations = []
        critical = [r for r in results if r["severity"] == "critical"]
        warning  = [r for r in results if r["severity"] == "warning"]
        ok_count = len(results) - len(critical) - len(warning)

        if critical:
            ge_crit = [r for r in critical if r["code"].upper().startswith("GE")]
            major_crit = [r for r in critical if r not in ge_crit]
            if ge_crit:
                codes_str = ", ".join(r["code"] for r in ge_crit[:5])
                recommendations.append(
                    f"🔴 {len(ge_crit)} GE subject(s) critically understaffed ({codes_str}). "
                    f"Consider hiring 2-3 visiting GE lecturers."
                )
            if major_crit:
                codes_str = ", ".join(r["code"] for r in major_crit[:5])
                recommendations.append(
                    f"🔴 {len(major_crit)} major subject(s) critically understaffed ({codes_str}). "
                    f"Need additional faculty with these specializations."
                )

        desg_limited = [r for r in results if any(
            i["status"] == "limited_by_designation" for i in r["instructors"]
        ) and r["severity"] in ("warning", "critical")]
        if desg_limited:
            recommendations.append(
                f"⚠️ {len(desg_limited)} subject(s) rely on designated faculty (Deans/Directors) with limited teaching hours. "
                f"Their effective capacity is reduced."
            )

        under = [w for w in instr_warnings if w["issue"] == "underspecialized"]
        if under:
            recommendations.append(
                f"💡 {len(under)} instructor(s) have ≤1 assignable subject. Consider cross-training for scheduling flexibility."
            )

        over = [w for w in instr_warnings if w["issue"] == "overspecialized"]
        if over:
            names = ", ".join(w["name"] for w in over[:3])
            recommendations.append(
                f"💡 {len(over)} instructor(s) spread thin across too many subjects ({names}). "
                f"Consider reducing to core specialties."
            )

        if not recommendations:
            recommendations.append("✅ Staffing levels look balanced for current block configuration.")

        return jsonify({
            "blocks": blocks,
            "semester": semester,
            "school_year": school_year,
            "summary": {
                "total_subjects": len(results),
                "critical": len(critical),
                "warning": len(warning),
                "ok": ok_count,
            },
            "subjects": results,
            "instructor_warnings": instr_warnings,
            "recommendations": recommendations,
        })

    except Exception as e:
        logger.error(f"Error in staffing analysis: {e}", exc_info=True)
        return jsonify({"detail": str(e)}), 500
    finally:
        db.close()
