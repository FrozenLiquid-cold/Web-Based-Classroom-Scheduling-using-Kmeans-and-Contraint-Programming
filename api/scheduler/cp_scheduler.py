"""OR-Tools Constraint Programming Scheduler with Cluster-based Processing"""
import logging
import os
import re
from typing import List, Dict, Optional, Set, Tuple, Any
from collections import defaultdict
from sqlalchemy.orm import Session
from ortools.sat.python import cp_model
from api import models
from api import db_procedures
from api.scheduler.timeslots import (
    TIME_BLOCKS,
    time_to_minutes,
    is_consecutive_blocks,
    get_all_time_slots,
)

logger = logging.getLogger(__name__)

# Optional: subject IDs for which we emit extra detailed debug logs (e.g.,
# unscheduled or problematic subjects such as OS 101 / CS Prof Elect 9).
DEBUG_SUBJECT_IDS: Set[int] = {66, 72, 78, 79, 85, 87}


class _SubjectBlockClone:
    """Lightweight in-memory clone used for per-block subject expansion.

    This avoids mutating SQLAlchemy model instances while allowing us to
    duplicate subjects per student block with synthetic IDs.
    """

    pass


# NSTP Special Scheduling Constants
NSTP_DAY_LABEL = "SUN"  # NSTP subjects are automatically scheduled on Sunday
NSTP_ROOM_NAME = "FIELD"  # NSTP subjects use FIELD room
NSTP_START_MIN = 480  # 8:00 AM in minutes
NSTP_END_MIN = 660  # 11:00 AM in minutes
NSTP_TIME_LABEL = "SUN 8:00–11:00"  # Display label for NSTP time slot

# Extended hours: allow evening slots up to 9PM
MAX_END_TIME_MIN = 1260  # 21:00 (9PM) in minutes


def _is_nstp_subject(subject) -> bool:
    """Check if a subject is NSTP (NSTP1, NSTP 2, NSTP 12, etc.)
    
    NSTP subjects get special handling:
    - Fixed day: Sunday
    - Fixed room: FIELD
    - Fixed time: 8:00 AM - 11:00 AM
    - All blocks share the same NSTP session (no per-block duplication)
    - Only instructor selection uses CP to avoid overlaps
    """
    code = getattr(subject, "code", "") or ""
    # Match NSTP1, NSTP 2, NSTP12, NSTP 12, etc.
    return code.upper().startswith("NSTP")


def _time_str_to_minutes(value: str) -> Optional[int]:
    value = (value or "").strip()
    if not value:
        return None
    match = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _parse_time_range_minutes(time_label: str):
    label = (time_label or "").strip()
    if not label:
        return None

    label = re.sub(r"^(M|T|W|TH|F)\s+", "", label, flags=re.IGNORECASE)
    normalized = (
        label.replace("—", "-")
        .replace("–", "-")
        .replace("−", "-")
    )

    match = re.match(r"^(\d+)\s*-\s*(\d+)$", normalized)
    if match:
        try:
            start_min = int(match.group(1))
            end_min = int(match.group(2))
        except Exception:
            return None
        if end_min <= start_min:
            return None
        return start_min, end_min

    parts = [p.strip() for p in normalized.split("-") if p.strip()]
    if len(parts) != 2:
        return None
    start_min = _time_str_to_minutes(parts[0])
    end_min = _time_str_to_minutes(parts[1])
    if start_min is None or end_min is None:
        return None
    if end_min <= start_min:
        return None
    return start_min, end_min


def _block_index_to_label(block_index: int) -> Optional[str]:
    """Convert a 1-based block index to a label: 1->"A", 2->"B", etc.

    Falls back to a generic label for indices beyond 26.
    """

    try:
        idx = int(block_index)
    except (TypeError, ValueError):
        return None
    if idx < 1:
        idx = 1
    if idx > 26:
        return f"BLOCK-{idx}"
    return chr(ord("A") + idx - 1)


DAY_LOAD_HARD_MIN = 2
DAY_LOAD_HARD_MAX = 5
DAY_LOAD_TARGET_MIN = 3
DAY_LOAD_TARGET_MAX = 4
DAY_TARGET_PENALTY_WEIGHT = 20
TIME_BAND_PENALTY_WEIGHT = 10
# Soft day preferences: weight for LEC/LAB day-of-week penalties
DAY_PREF_PENALTY_WEIGHT = 5

# Primary objective weight: reward per scheduled subject. This is set high enough
# that, in an otherwise empty timetable, the solver strongly prefers scheduling
# all feasible subjects rather than dropping them just to reduce soft penalties
# (day balance, time bands, early-start avoidance, etc.).
SCHEDULE_REWARD_WEIGHT = 10000
INSTRUCTOR_MAX_BLOCKS_PER_DAY = 5
INSTRUCTOR_MIN_BREAK_MIN = 60

TIME_BANDS = [
    {
        "label": "early",
        "min": 7 * 60,
        "max": 9 * 60,
        "min_count": 0,
        "max_count": 2,
    },
    {
        "label": "morning",
        "min": 9 * 60,
        "max": 12 * 60,
        "min_count": 6,
        "max_count": 8,
    },
    {
        "label": "afternoon",
        "min": 12 * 60,
        "max": 16 * 60,
        "min_count": 5,
        "max_count": 6,
    },
    {
        "label": "late_afternoon",
        "min": 16 * 60,
        "max": 19 * 60,
        "min_count": 3,
        "max_count": 4,
    },
    {
        "label": "evening",
        "min": 19 * 60,
        "max": 21 * 60,
        "min_count": 0,
        "max_count": 3,
    },
]


def log_once(msg: str, _logged=set()):
    if msg not in _logged:
        logger.warning(msg)
        _logged.add(msg)


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def _range_conflicts(booked_ranges: Dict[Tuple[Any, int], List[Tuple[int, int]]], resource_key: Any, day_id: int, start_min: int, end_min: int) -> bool:
    try:
        day_id_int = int(day_id)
        start_i = int(start_min)
        end_i = int(end_min)
    except Exception:
        return False
    for bs, be in booked_ranges.get((resource_key, day_id_int), []):
        if _ranges_overlap(start_i, end_i, bs, be):
            return True
    return False


# --- BEGIN REWRITE: robust start-option generation and safe CP var creation ---

def is_consecutive_slot_indexes(slot_list: List[Dict]) -> bool:
    """Check if slot indexes are consecutive (existing util pattern)."""
    if not slot_list:
        return False
    indexes = [s["index"] for s in slot_list]
    return all(indexes[i] + 1 == indexes[i + 1] for i in range(len(indexes) - 1))


def is_consecutive_slots_in_time(slot_list: List[Dict]) -> bool:
    """
    STRICT CHECK: Verify slots are consecutive in actual time, not just by index.
    This prevents gaps in the schedule (e.g., missing 11:30-1:00 slot).
    
    Returns True only if:
    1. Slot indexes are consecutive
    2. Each slot's start_min equals the previous slot's end_min (no time gaps)
    """
    if not slot_list or len(slot_list) < 2:
        return True  # Single slot or empty is always "consecutive"
    
    # First check: indexes must be consecutive
    indexes = [s["index"] for s in slot_list]
    if not all(indexes[i] + 1 == indexes[i + 1] for i in range(len(indexes) - 1)):
        return False
    
    # Second check: actual time must be consecutive (no gaps)
    for i in range(len(slot_list) - 1):
        current_slot = slot_list[i]
        next_slot = slot_list[i + 1]
        
        # Current slot's end_min must equal next slot's start_min
        if current_slot["end_min"] != next_slot["start_min"]:
            return False
    
    return True


def compute_window_duration_minutes(block_slots: List[Dict]) -> int:
    """Return the real duration in minutes of a consecutive block of slots."""
    # sum each slot duration (end_min - start_min) — robust for non-uniform grids
    return sum(slot["end_min"] - slot["start_min"] for slot in block_slots)


# def generate_real_start_windows_for_subject(
#     subject,
#     day_slots: List[Dict],
#     slot_to_block_map: Dict[Tuple[int, int], int],
#     day_id: int,
#     sampling: int = 1,
# ) -> List[Dict]:
#     """
#     Generate all valid windows (start positions) for the subject on a single day.
#     - subject must expose: recommended_slots/min_slots/max_slots OR subject.session_minutes
#     - day_slots is the list of 30-min slot dicts for that day
#     - sampling controls step: 1 = examine every start_pos, >1 skips positions for performance (use with care)
#     Returns a list of option dicts (no CP variables included).
#     """
#     options = []

#     # determine required duration in slots:
#     # Prefer an explicit minute duration if available, else fall back to slots mapping
#     if getattr(subject, "session_minutes", None) is not None:
#         duration_min = int(subject.session_minutes)
#         # convert minutes to number of 30-min slots (ceiling)
#         num_slots = (duration_min + 29) // 30
#     else:
#         # fallback to slots-based fields you already had
#         rec_slots = getattr(subject, "recommended_slots", None) or getattr(subject, "min_slots", 1)
#         min_slots = getattr(subject, "min_slots", None) or rec_slots
#         max_slots = getattr(subject, "max_slots", None) or rec_slots
#         # generate windows for all allowed slot counts
#         # We'll iterate over each num_slots below
#         duration_min = None
#         # use slot_counts list with a deterministic order
#         slot_counts = list(range(min_slots, max_slots + 1))
#         if not slot_counts:
#             slot_counts = [rec_slots]

#     # Unified iteration for either a single duration_min or slot_counts
#     if duration_min is not None:
#         # single duration case (preferred)
#         num_slots = (duration_min + 29) // 30
#         max_start_pos = len(day_slots) - num_slots
#         if max_start_pos < 0:
#             return []
#         for start_pos in range(0, max_start_pos + 1, sampling):
#             block_slots = day_slots[start_pos : start_pos + num_slots]
#             if len(block_slots) != num_slots:
#                 continue
#             # STRICT CHECK: Verify slots are consecutive in both index AND actual time
#             if not is_consecutive_slots_in_time(block_slots):
#                 continue
#             # compute real start/end/min/duration
#             start_min = block_slots[0]["start_min"]
#             # duration always tied to intended slot count (each slot is 30 minutes)
#             duration_min = num_slots * 30
#             # Calculate end_min from start_min + duration (ensures correctness)
#             end_min = start_min + duration_min
#             # Verify the last slot's end_min matches our calculated end_min
#             actual_end_min = block_slots[-1]["end_min"]
#             if actual_end_min != end_min:
#                 # This should never happen if is_consecutive_slots_in_time passed, but log if it does
#                 logger.warning(f"Slot continuity check passed but end_min mismatch: "
#                              f"calculated={end_min}, actual={actual_end_min}, num_slots={num_slots}")
#                 continue
#             # build block_indices via slot_to_block_map
#             block_ids = []
#             blocks_spanned = []
#             unmapped_slot_count = 0
#             for slot in block_slots:
#                 bid = slot_to_block_map.get((day_id, slot["start_min"]))
#                 if bid is not None:
#                     blocks_spanned.append(bid)
#                     block_ids.append(bid)
#                 else:
#                     unmapped_slot_count += 1
            
#             if not blocks_spanned:
#                 # cannot map to DB blocks — skip
#                 # Log first few occurrences to help debug
#                 if unmapped_slot_count > 0 and len(options) < 3:
#                     logger.debug(
#                         "Skipping option: %d/%d slots unmapped for subject %s, day %d, start_min=%d",
#                         unmapped_slot_count, len(block_slots),
#                         getattr(subject, "code", "?"), day_id, start_min
#                     )
#                 continue
            
#             # Validate: All slots should be mapped (warn if some are missing)
#             if unmapped_slot_count > 0:
#                 logger.warning(
#                     "Partial block mapping: Subject %s, day %d: %d/%d slots mapped. "
#                     "Unmapped slots may cause scheduling issues.",
#                     getattr(subject, "code", "?"), day_id, len(blocks_spanned), len(block_slots)
#                 )

#             # Validate duration calculation consistency
#             calculated_duration = end_min - start_min
#             if abs(duration_min - calculated_duration) > 1:  # Allow 1 minute tolerance
#                 logger.warning(
#                     "[DURATION MISMATCH] Subject %s, day %d: stored duration_min=%d vs calculated=%d "
#                     "(start_min=%d, end_min=%d, num_slots=%d). Using calculated duration.",
#                     getattr(subject, "code", "?"), day_id, duration_min, calculated_duration,
#                     start_min, end_min, num_slots
#                 )
#                 duration_min = calculated_duration
            
#             options.append({
#                 "day_id": day_id,
#                 "start_min": start_min,
#                 "end_min": end_min,
#                 "duration_min": duration_min,  # Use validated duration
#                 "num_slots": num_slots,
#                 "slot_indexes": [s["index"] for s in block_slots],
#                 "slot_labels": [s["label"] for s in block_slots],
#                 "blocks_spanned": blocks_spanned,
#             })
#     else:
#         # multiple slot_counts allowed
#         for num_slots in slot_counts:
#             max_start_pos = len(day_slots) - num_slots
#             if max_start_pos < 0:
#                 continue
#             for start_pos in range(0, max_start_pos + 1, sampling):
#                 block_slots = day_slots[start_pos : start_pos + num_slots]
#                 if len(block_slots) != num_slots:
#                     continue
#                 # STRICT CHECK: Verify slots are consecutive in both index AND actual time
#                 if not is_consecutive_slots_in_time(block_slots):
#                     continue
#                 start_min = block_slots[0]["start_min"]
#                 # duration always tied to intended slot count (each slot is 30 minutes)
#                 duration_min = num_slots * 30
#                 # Calculate end_min from start_min + duration (ensures correctness)
#                 end_min = start_min + duration_min
#                 # Verify the last slot's end_min matches our calculated end_min
#                 actual_end_min = block_slots[-1]["end_min"]
#                 if actual_end_min != end_min:
#                     # This should never happen if is_consecutive_slots_in_time passed, but log if it does
#                     logger.warning(f"Slot continuity check passed but end_min mismatch: "
#                                  f"calculated={end_min}, actual={actual_end_min}, num_slots={num_slots}")
#                     continue
#                 block_ids = []
#                 blocks_spanned = []
#                 unmapped_slot_count = 0
#                 for slot in block_slots:
#                     bid = slot_to_block_map.get((day_id, slot["start_min"]))
#                     if bid is not None:
#                         blocks_spanned.append(bid)
#                         block_ids.append(bid)
#                     else:
#                         unmapped_slot_count += 1
#                 if not blocks_spanned:
#                     continue
                
#                 # Validate: All slots should be mapped (warn if some are missing)
#                 if unmapped_slot_count > 0:
#                     logger.warning(
#                         "Partial block mapping: Subject %s, day %d: %d/%d slots mapped. "
#                         "Unmapped slots may cause scheduling issues.",
#                         getattr(subject, "code", "?"), day_id, len(blocks_spanned), len(block_slots)
#                     )
                
#                 # Validate duration calculation consistency
#                 calculated_duration = end_min - start_min
#                 if abs(duration_min - calculated_duration) > 1:  # Allow 1 minute tolerance
#                     logger.warning(
#                         "[DURATION MISMATCH] Subject %s, day %d: stored duration_min=%d vs calculated=%d "
#                         "(start_min=%d, end_min=%d, num_slots=%d). Using calculated duration.",
#                         getattr(subject, "code", "?"), day_id, duration_min, calculated_duration,
#                         start_min, end_min, num_slots
#                     )
#                     duration_min = calculated_duration

#                 options.append({
#                     "day_id": day_id,
#                     "start_min": start_min,
#                     "end_min": end_min,
#                     "duration_min": duration_min,  # Use validated duration
#                     "num_slots": num_slots,
#                     "slot_indexes": [s["index"] for s in block_slots],
#                     "slot_labels": [s["label"] for s in block_slots],
#                     "blocks_spanned": blocks_spanned,
#                 })

#     return options

def generate_all_subject_start_options(
    subjects: List,
    days: List,
    slots_by_day: Dict[str, List[Dict]],
    slot_to_block_map: Dict[Tuple[int, int], int],
    sampling: int = 1,
) -> Dict[int, List[Dict]]:
    """
    For all subjects, compute valid start windows using the updated LEC/LAB pattern logic.
    Returns {subject_id: [option_dicts...]}

    Rules:
    - LEC subjects: Only MW, TTh, or F patterns
    - LAB subjects: Single meeting on any day, but still restricted to MW, TTh, or F patterns
    """
    all_options = defaultdict(list)

    # DEBUG: Verify slots_by_day has entries for all days
    day_labels_in_slots = set(slots_by_day.keys())
    day_labels_expected = {d.label for d in days}
    if day_labels_in_slots != day_labels_expected:
        logger.warning(
            "MISMATCH: slots_by_day has days %s but expected %s. "
            "Missing days: %s, Extra days: %s",
            sorted(day_labels_in_slots),
            sorted(day_labels_expected),
            sorted(day_labels_expected - day_labels_in_slots),
            sorted(day_labels_in_slots - day_labels_expected)
        )
    else:
        logger.debug("✓ slots_by_day has entries for all %d days: %s",
                     len(day_labels_expected), sorted(day_labels_expected))

    # Generate options per subject
    for subj in subjects:
        subj_id = int(subj.id)
        subject_options = generate_subject_start_options(
            subject=subj,
            slots_by_day=slots_by_day,
            slot_to_block_map=slot_to_block_map,
            days=days,
            logger=logger
        )

        # Attach metadata and validate blocks_by_day
        for opt in subject_options:
            opt["subject_id"] = subj_id
            opt["subject"] = subj

            blocks_by_day = opt.get("blocks_by_day", {})
            if not blocks_by_day:
                logger.warning(
                    "Subject %d option missing blocks_by_day, constructing from block_indices",
                    subj_id
                )
                day_ids = opt.get("day_ids", [opt.get("day_id")])
                block_indices = opt.get("block_indices", set())
                opt["blocks_by_day"] = {d_id: block_indices for d_id in day_ids}

            assert all(len(b) > 0 for b in blocks_by_day.values()), \
                f"Subject {subj_id}: blocks_by_day contains empty sets: {blocks_by_day}"

            all_options[subj_id].append(opt)

    # DEBUG: Log which days each subject can be scheduled on
    day_id_to_label = {d.id: d.label for d in days}
    for subj_id, opts in all_options.items():
        days_used = set()
        day_labels_used = set()
        pattern_counts = {"MW": 0, "TTh": 0, "F": 0, "LAB": 0, "OTHER": 0}

        for opt in opts:
            opt_days = opt.get("days", [])
            if opt_days == ["M", "W"]:
                pattern_counts["MW"] += 1
            elif opt_days == ["T", "TH"]:
                pattern_counts["TTh"] += 1
            elif opt_days == ["F"]:
                pattern_counts["F"] += 1
            elif len(opt_days) == 1 and opt_days[0] in ["M", "T", "W", "TH", "F"]:
                pattern_counts["LAB"] += 1
            else:
                pattern_counts["OTHER"] += 1

            if "day_ids" in opt:
                days_used.update(opt["day_ids"])
                day_labels_used.update([day_id_to_label.get(did, "?") for did in opt["day_ids"]])
            elif "day_id" in opt:
                days_used.add(opt["day_id"])
                day_labels_used.add(day_id_to_label.get(opt["day_id"], "?"))

        pattern_summary = ", ".join([f"{k}:{v}" for k, v in pattern_counts.items() if v > 0])

        logger.info(
            "SUBJECT %d - %d options | Days: %s (labels: %s) | Patterns: %s",
            subj_id, len(opts), sorted(days_used), sorted(day_labels_used), pattern_summary
        )

    # Summary: Check if any subjects have no options
    subjects_with_no_options = [sid for sid, opts in all_options.items() if not opts]
    if subjects_with_no_options:
        logger.error(
            "CRITICAL: %d subjects have NO scheduling options: %s. "
            "This will cause scheduling failures.",
            len(subjects_with_no_options), subjects_with_no_options[:10]
        )

    return all_options



def _find_matching_slot(day_slots: List[Dict[str, Any]], template_slot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a slot from day_slots that has the same start_min and duration as template_slot.

    day_slots: list of slot dicts for the target day
    template_slot: slot dict to match against (expects keys 'start_min' and 'duration')
    """
    template_start = template_slot.get("start_min")
    template_end = template_slot.get("end_min")
    for slot in day_slots:
        if slot.get("start_min") == template_start and slot.get("end_min") == template_end:
            return slot
    return None



def generate_subject_start_options(
    subject: Any,
    slots_by_day: Dict[str, List[Dict[str, Any]]],
    slot_to_block_map: Dict[Tuple[int, int], int],
    days: List,
    logger: Any = None,
) -> List[Dict[str, Any]]:
    """
    Generate start options for a single subject with detailed debug logging.
    
    Args:
        subject: The subject to schedule
        slots_by_day: Available time slots by day
        slot_to_block_map: Maps (day_id, start_min) to block index
        days: List of day objects
        logger: Optional logger for debug output
    
    Returns:
        List of valid scheduling options with detailed timing information
    """
    def debug_log(msg: str, level: str = 'debug') -> None:
        """Helper for consistent debug logging"""
        if logger:
            subj_id = getattr(subject, 'id', '?')
            subj_code = getattr(subject, 'code', '?')
            log_msg = f"[Subj {subj_id} {subj_code}] {msg}"
            if level == 'warning':
                logger.warning(log_msg)
            elif level == 'error':
                logger.error(log_msg)
            else:
                logger.debug(log_msg)
    """
    Generate start options for a single subject according to rules:

    - LEC: only MW (Mon+Wed), TTh (Tue+Thu), or F (Friday)
    - LAB: single meeting on any day, but must follow allowed patterns (MW, TTh, F)

    Returns list of option dicts with keys:
        'days', 'day_ids', 'start_min', 'end_min', 'duration_min',
        'block_indices', 'blocks_by_day', 'slot_indexes', 'blocks_spanned', 'slot_labels', 'num_slots'
    """
    options: List[Dict[str, Any]] = []

    # Short day names
    MON, TUE, WED, THU, FRI = "M", "T", "W", "TH", "F"
    allowed_days = [MON, TUE, WED, THU, FRI]
    
    # Debug: Log input parameters
    # Safely get subject attributes with defaults
    subject_type = getattr(subject, 'subject_type', '?')
    hours_lec = getattr(subject, 'hours_lec', 0) or 0
    hours_lab = getattr(subject, 'hours_lab', 0) or 0
    
    debug_log(f"Generating start options. Subject type: {subject_type}")
    debug_log(f"Subject hours - LEC: {hours_lec}, LAB: {hours_lab}")
    debug_log(f"Available days: {', '.join(slots_by_day.keys())}")
    
    # Track day availability
    day_label_to_day = {d.label: d for d in days}
    for day_label in allowed_days:
        debug_log(f"Day {day_label}: {len(slots_by_day.get(day_label, []))} slots available")

    # Detect type
    if hasattr(subject, "type"):
        subj_type = str(subject.type).upper().strip()
    elif isinstance(subject, dict):
        subj_type = str(subject.get("type", "")).upper().strip()
    else:
        subj_type = ""
    
    debug_log(f"Subject type detected as: {subj_type}")
    
    # Get hours_lec and hours_lab with fallbacks (already done above)
    total_hours = hours_lec + hours_lab
    debug_log(f"Total hours to schedule: {total_hours} (LEC: {hours_lec}, LAB: {hours_lab})")
    
    # Log available attributes (safely)
    try:
        debug_log(f"Subject has attributes: {', '.join([attr for attr in dir(subject) if not attr.startswith('_')])}")
    except Exception as e:
        debug_log(f"Could not list subject attributes: {str(e)}", level='warning')

    subj_id = getattr(subject, "id", "?")

    if logger:
        logger.debug("generate_subject_start_options: Subject %s type='%s'", subj_id, subj_type)

    # --- LAB logic: MW, TTh, F using LAB-only windows ---
    if subj_type == "LAB":
        debug_log("Processing as LAB subject (MW/TTh/F patterns)")

        mon_day = day_label_to_day.get(MON)
        wed_day = day_label_to_day.get(WED)
        tue_day = day_label_to_day.get(TUE)
        thu_day = day_label_to_day.get(THU)
        fri_day = day_label_to_day.get(FRI)

        # Pattern MW (LAB) - uses all blocks on M/W; lab-vs-lec is enforced via
        # room/instructor eligibility, not via is_lab on the time grid.
        if mon_day and wed_day and MON in slots_by_day and WED in slots_by_day:
            debug_log("Generating MW LAB patterns")
            for mon_slot in slots_by_day[MON]:
                wed_slot = _find_matching_slot(slots_by_day[WED], mon_slot)
                if wed_slot is None:
                    continue

                mon_slot_indexes = mon_slot.get("index", [])
                wed_slot_indexes = wed_slot.get("index", [])
                if isinstance(mon_slot_indexes, int):
                    mon_slot_indexes = [mon_slot_indexes]
                if isinstance(wed_slot_indexes, int):
                    wed_slot_indexes = [wed_slot_indexes]

                mon_block_indices = set(mon_slot.get("block_indices", []))
                wed_block_indices = set(wed_slot.get("block_indices", []))
                if not mon_block_indices:
                    mon_block_indices = {mon_slot_indexes[0]} if mon_slot_indexes else set()
                if not wed_block_indices:
                    wed_block_indices = {wed_slot_indexes[0]} if wed_slot_indexes else set()

                block_indices = mon_block_indices | wed_block_indices
                all_slot_indexes = mon_slot_indexes + wed_slot_indexes

                start_min = mon_slot.get("start_min")
                end_min = mon_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [MON, WED],
                    "day_ids": [mon_day.id, wed_day.id],
                    "day_id": mon_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": block_indices,
                    "blocks_by_day": {mon_day.id: mon_block_indices, wed_day.id: wed_block_indices},
                    "slot_indexes": all_slot_indexes,
                    "blocks_spanned": set(mon_slot.get("blocks_spanned", [])) | set(wed_slot.get("blocks_spanned", [])),
                    "slot_labels": [mon_slot.get("label", ""), wed_slot.get("label", "")],
                    "num_slots": len(all_slot_indexes),
                })

        # Pattern TTh (LAB)
        if tue_day and thu_day and TUE in slots_by_day and THU in slots_by_day:
            debug_log("Generating TTh LAB patterns")
            for tue_slot in slots_by_day[TUE]:
                thu_slot = _find_matching_slot(slots_by_day[THU], tue_slot)
                if thu_slot is None:
                    continue

                tue_slot_indexes = tue_slot.get("index", [])
                thu_slot_indexes = thu_slot.get("index", [])
                if isinstance(tue_slot_indexes, int):
                    tue_slot_indexes = [tue_slot_indexes]
                if isinstance(thu_slot_indexes, int):
                    thu_slot_indexes = [thu_slot_indexes]

                tue_block_indices = set(tue_slot.get("block_indices", []))
                thu_block_indices = set(thu_slot.get("block_indices", []))
                if not tue_block_indices:
                    tue_block_indices = {tue_slot_indexes[0]} if tue_slot_indexes else set()
                if not thu_block_indices:
                    thu_block_indices = {thu_slot_indexes[0]} if thu_slot_indexes else set()

                block_indices = tue_block_indices | thu_block_indices
                all_slot_indexes = tue_slot_indexes + thu_slot_indexes

                start_min = tue_slot.get("start_min")
                end_min = tue_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [TUE, THU],
                    "day_ids": [tue_day.id, thu_day.id],
                    "day_id": tue_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": block_indices,
                    "blocks_by_day": {tue_day.id: tue_block_indices, thu_day.id: thu_block_indices},
                    "slot_indexes": all_slot_indexes,
                    "blocks_spanned": set(tue_slot.get("blocks_spanned", [])) | set(thu_slot.get("blocks_spanned", [])),
                    "slot_labels": [tue_slot.get("label", ""), thu_slot.get("label", "")],
                    "num_slots": len(all_slot_indexes),
                })

        # Pattern F (single-day LAB) - single-day is allowed only on Friday.
        if fri_day and FRI in slots_by_day:
            debug_log("Generating F LAB patterns")
            for fri_slot in slots_by_day[FRI]:
                slot_indexes = fri_slot.get("index", [])
                if isinstance(slot_indexes, int):
                    slot_indexes = [slot_indexes]
                block_indices = set(fri_slot.get("block_indices", []))
                if not block_indices:
                    block_indices = {slot_indexes[0]} if slot_indexes else set()

                start_min = fri_slot.get("start_min")
                end_min = fri_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [FRI],
                    "day_ids": [fri_day.id],
                    "day_id": fri_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": block_indices,
                    "blocks_by_day": {fri_day.id: block_indices},
                    "slot_indexes": slot_indexes,
                    "blocks_spanned": set(fri_slot.get("blocks_spanned", [])),
                    "slot_labels": [fri_slot.get("label", "")],
                    "num_slots": len(slot_indexes),
                })

        if logger:
            logger.debug(
                "generate_subject_start_options: Subject %s (LAB) -> %d MW/TTh/F LAB options",
                subj_id,
                len(options),
            )

        # Extra per-option logging for debug subjects (e.g. unscheduled ones)
        try:
            subj_id_int = int(subj_id)
        except Exception:
            subj_id_int = None
        if subj_id_int is not None and subj_id_int in DEBUG_SUBJECT_IDS and logger:
            for opt in options:
                days = opt.get("days")
                start_min = opt.get("start_min")
                end_min = opt.get("end_min")
                duration_min = opt.get("duration_min")
                slot_labels = opt.get("slot_labels")
                logger.info(
                    "[DEBUG OPTIONS] LAB subject %s code=%s days=%s time=%s (%d-%d, dur=%d)",
                    subj_id_int,
                    getattr(subject, "code", ""),
                    days,
                    slot_labels or "N/A",
                    start_min,
                    end_min,
                    duration_min,
                )
        return options

    # --- LEC logic: MW, TTh, F ---
    if subj_type == "LEC":
        if logger:
            logger.info("generate_subject_start_options: Subject %s is LEC - generating MW/TTh/F patterns ONLY", subj_id)

        mon_day = day_label_to_day.get(MON)
        wed_day = day_label_to_day.get(WED)
        tue_day = day_label_to_day.get(TUE)
        thu_day = day_label_to_day.get(THU)
        fri_day = day_label_to_day.get(FRI)

        # Pattern MW
        if mon_day and wed_day and MON in slots_by_day and WED in slots_by_day:
            for mon_slot in slots_by_day[MON]:
                wed_slot = _find_matching_slot(slots_by_day[WED], mon_slot)
                if wed_slot is None:
                    continue

                mon_slot_indexes = mon_slot.get("index", [])
                wed_slot_indexes = wed_slot.get("index", [])
                if isinstance(mon_slot_indexes, int):
                    mon_slot_indexes = [mon_slot_indexes]
                if isinstance(wed_slot_indexes, int):
                    wed_slot_indexes = [wed_slot_indexes]

                mon_block_indices = set(mon_slot.get("block_indices", []))
                wed_block_indices = set(wed_slot.get("block_indices", []))
                if not mon_block_indices:
                    mon_block_indices = {mon_slot_indexes[0]} if mon_slot_indexes else set()
                if not wed_block_indices:
                    wed_block_indices = {wed_slot_indexes[0]} if wed_slot_indexes else set()

                block_indices = mon_block_indices | wed_block_indices
                all_slot_indexes = mon_slot_indexes + wed_slot_indexes

                start_min = mon_slot.get("start_min")
                end_min = mon_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [MON, WED],
                    "day_ids": [mon_day.id, wed_day.id],
                    "day_id": mon_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": block_indices,
                    "blocks_by_day": {mon_day.id: mon_block_indices, wed_day.id: wed_block_indices},
                    "slot_indexes": all_slot_indexes,
                    "blocks_spanned": set(mon_slot.get("blocks_spanned", [])) | set(wed_slot.get("blocks_spanned", [])),
                    "slot_labels": [mon_slot.get("label", ""), wed_slot.get("label", "")],
                    "num_slots": len(all_slot_indexes),
                })

        # Pattern TTh
        if tue_day and thu_day and TUE in slots_by_day and THU in slots_by_day:
            for tue_slot in slots_by_day[TUE]:
                thu_slot = _find_matching_slot(slots_by_day[THU], tue_slot)
                if thu_slot is None:
                    continue

                tue_slot_indexes = tue_slot.get("index", [])
                thu_slot_indexes = thu_slot.get("index", [])
                if isinstance(tue_slot_indexes, int):
                    tue_slot_indexes = [tue_slot_indexes]
                if isinstance(thu_slot_indexes, int):
                    thu_slot_indexes = [thu_slot_indexes]

                tue_block_indices = set(tue_slot.get("block_indices", []))
                thu_block_indices = set(thu_slot.get("block_indices", []))
                if not tue_block_indices:
                    tue_block_indices = {tue_slot_indexes[0]} if tue_slot_indexes else set()
                if not thu_block_indices:
                    thu_block_indices = {thu_slot_indexes[0]} if thu_slot_indexes else set()

                block_indices = tue_block_indices | thu_block_indices
                all_slot_indexes = tue_slot_indexes + thu_slot_indexes

                start_min = tue_slot.get("start_min")
                end_min = tue_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [TUE, THU],
                    "day_ids": [tue_day.id, thu_day.id],
                    "day_id": tue_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": block_indices,
                    "blocks_by_day": {tue_day.id: tue_block_indices, thu_day.id: thu_block_indices},
                    "slot_indexes": all_slot_indexes,
                    "blocks_spanned": set(tue_slot.get("blocks_spanned", [])) | set(thu_slot.get("blocks_spanned", [])),
                    "slot_labels": [tue_slot.get("label", ""), thu_slot.get("label", "")],
                    "num_slots": len(all_slot_indexes),
                })

        # Pattern F
        # NOTE: Disabled for LEC subjects to enforce MW/TTh-only lecture patterns.
        if fri_day and FRI in slots_by_day:
            for fri_slot in slots_by_day[FRI]:
                slot_indexes = fri_slot.get("index", [])
                if isinstance(slot_indexes, int):
                    slot_indexes = [slot_indexes]
                block_indices = set(fri_slot.get("block_indices", []))
                if not block_indices:
                    block_indices = {slot_indexes[0]} if slot_indexes else set()
                start_min = fri_slot.get("start_min")
                end_min = fri_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [FRI],
                    "day_ids": [fri_day.id],
                    "day_id": fri_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": block_indices,
                    "blocks_by_day": {fri_day.id: block_indices},
                    "slot_indexes": slot_indexes,
                    "blocks_spanned": set(fri_slot.get("blocks_spanned", [])),
                    "slot_labels": [fri_slot.get("label", "")],
                    "num_slots": len(slot_indexes),
                })

        if logger:
            logger.info("generate_subject_start_options: Subject %s (LEC) -> %d options", subj_id, len(options))

        # Extra per-option logging for debug subjects (e.g. unscheduled ones)
        try:
            subj_id_int = int(subj_id)
        except Exception:
            subj_id_int = None
        if subj_id_int is not None and subj_id_int in DEBUG_SUBJECT_IDS and logger:
            for opt in options:
                days = opt.get("days")
                start_min = opt.get("start_min")
                end_min = opt.get("end_min")
                duration_min = opt.get("duration_min")
                slot_labels = opt.get("slot_labels")
                logger.info(
                    "[DEBUG OPTIONS] LEC subject %s code=%s days=%s time=%s (%d-%d, dur=%d)",
                    subj_id_int,
                    getattr(subject, "code", ""),
                    days,
                    slot_labels or "N/A",
                    start_min,
                    end_min,
                    duration_min,
                )
        return options

    # --- fallback for unknown types ---
    for day_label, day_slots in slots_by_day.items():
        day_obj = day_label_to_day.get(day_label)
        if not day_obj:
            continue
        for slot in day_slots:
            slot_indexes = slot.get("index", [])
            if isinstance(slot_indexes, int):
                slot_indexes = [slot_indexes]
            block_indices = set(slot.get("block_indices", []))
            if not block_indices:
                block_indices = {slot_indexes[0]} if slot_indexes else set()
            start_min = slot.get("start_min")
            end_min = slot.get("end_min")
            duration_min = end_min - start_min

            options.append({
                "days": [day_label],
                "day_ids": [day_obj.id],
                "day_id": day_obj.id,
                "start_min": start_min,
                "end_min": end_min,
                "duration_min": duration_min,
                "block_indices": block_indices,
                "blocks_by_day": {day_obj.id: block_indices},
                "slot_indexes": slot_indexes,
                "blocks_spanned": set(slot.get("blocks_spanned", [])),
                "slot_labels": [slot.get("label", "")],
                "num_slots": len(slot_indexes),
            })

    if logger:
        logger.debug("generate_subject_start_options: Subject %s -> fallback options=%d", subj_id, len(options))
    return options



def build_eligibility_maps(
    subjects: List[models.Subject],
    instructors: List[models.Instructor],
    rooms: List[models.Room],
    db: Session = None
) -> Tuple[Dict[int, List[int]], Dict[int, List[int]]]:
    """
    Build instructor and room eligibility PER SUBJECT SECTION.
    Keys are subject.id (NOT course_id).
    """

    # Final maps (correct)
    subject_to_instructors: Dict[int, List[int]] = defaultdict(list)
    subject_to_rooms: Dict[int, List[int]] = defaultdict(list)

    # ---------------------------------------------------------
    # Load course → college_id mapping (only if DB session provided)
    # ---------------------------------------------------------
    course_college_map = {}
    if db:
        course_ids = {s.course_id for s in subjects if s.course_id}
        if course_ids:
            courses = (
                db.query(models.Course)
                .filter(models.Course.id.in_(course_ids))
                .all()
            )
            course_college_map = {c.id: c.college_id for c in courses}

    # ---------------------------------------------------------
    # Build eligibility PER SUBJECT
    # ---------------------------------------------------------
    for subject in subjects:
        sid = subject.id
        subj_code = (subject.code or "").upper().strip()
        subj_type = (subject.type or "").upper().strip()
        subj_course_id = subject.course_id
        subj_college = course_college_map.get(subj_course_id)

        eligible_instrs: List[int] = []
        eligible_rooms: List[int] = []
        sp_instr_count = 0
        sp_room_count = 0

        if db is not None:
            try:
                base_sid_val = getattr(subject, "original_subject_id", sid)
                base_sid = int(base_sid_val) if base_sid_val is not None else sid
            except Exception:
                base_sid = sid

            try:
                db_instrs = db_procedures.get_instructor_eligibility(db, base_sid)
                eligible_instrs = [inst.id for inst in db_instrs]
                sp_instr_count = len(eligible_instrs)
            except Exception as e:
                logger.warning(
                    "build_eligibility_maps: instructor eligibility SP failed for subject %s (ID=%s, base_sid=%s): %s",
                    subj_code,
                    sid,
                    base_sid,
                    e,
                )
                eligible_instrs = []

            try:
                db_rooms = db_procedures.get_room_eligibility(db, base_sid)
                eligible_rooms = [room.id for room in db_rooms]
                sp_room_count = len(eligible_rooms)
            except Exception as e:
                logger.warning(
                    "build_eligibility_maps: room eligibility SP failed for subject %s (ID=%s, base_sid=%s): %s",
                    subj_code,
                    sid,
                    base_sid,
                    e,
                )
                eligible_rooms = []

            if sid in {16, 17, 27, 28, 32} or base_sid in {16, 17, 27, 28, 32}:
                logger.info(
                    "Eligibility SP debug: subject %s (sid=%s, base_sid=%s): sp_instr=%d, sp_rooms=%d",
                    subj_code,
                    sid,
                    base_sid,
                    sp_instr_count,
                    sp_room_count,
                )

        if not eligible_instrs:
            eligible_instrs = []

            for inst in instructors:
                inst_id = inst.id
                inst_college = inst.college_id
                assignable = inst.assignable_courses or ""
                assignable_set = {c.strip().upper() for c in assignable.split(",") if c.strip()}

                matched = False

                if assignable_set and subj_code in assignable_set:
                    matched = True
                elif subj_college and inst_college and subj_college == inst_college:
                    matched = True
                elif not assignable_set and not subj_college and not inst_college:
                    matched = True

                if matched:
                    eligible_instrs.append(inst_id)

        subject_to_instructors[sid] = eligible_instrs

        if not eligible_rooms:
            eligible_rooms = []
            for room in rooms:
                room_type = (room.type or "").upper().strip()
                if room_type == subj_type:
                    eligible_rooms.append(room.id)

        # CRITICAL: Exclude FIELD room for non-NSTP subjects
        # FIELD is reserved exclusively for NSTP subjects
        if not _is_nstp_subject(subject):
            field_room_ids = [room.id for room in rooms if (room.name or "").upper() == "FIELD"]
            if field_room_ids:
                eligible_rooms = [rid for rid in eligible_rooms if rid not in field_room_ids]

        subject_to_rooms[sid] = eligible_rooms

    # ---------------------------------------------------------
    # Logging summary
    # ---------------------------------------------------------
    instr_nonempty = sum(1 for s in subject_to_instructors if subject_to_instructors[s])
    rooms_nonempty = sum(1 for s in subject_to_rooms if subject_to_rooms[s])

    logger.info(
        "Built per-subject eligibility: subjects_with_instr=%d/%d, subjects_with_rooms=%d/%d",
        instr_nonempty, len(subjects),
        rooms_nonempty, len(subjects)
    )

    return dict(subject_to_instructors), dict(subject_to_rooms)


def get_existing_bookings(
    db: Session,
    years: Optional[List[int]],
    semester: int,
    exclude_course_id: Optional[int] = None,
    slots_by_day: Optional[Dict[str, List[Dict]]] = None,
    day_id_map: Optional[Dict[str, int]] = None
) -> Tuple[Set[Tuple[str, int, int]], Set[Tuple[int, int, int]]]:
    """
    Get existing room and instructor bookings from database using stored procedure.
    Converts time_label to block_index for efficient numeric conflict checking.
    Optimized with PostgreSQL stored procedure for better performance.
    
    Args:
        db: Database session
        years: List of year levels
        semester: Semester (1-2)
        exclude_course_id: Optional course ID to exclude
        slots_by_day: Optional dict mapping day labels to slot lists (for conversion)
        day_id_map: Optional dict mapping day labels to day IDs (for conversion)
    
    Returns:
        (booked_room_slots, booked_instr_slots) where slots are (resource_name/resource_id, day_id, block_index)
    """
    booked_room_slots = set()   # (room_name, day_id, block_index)
    booked_instr_slots = set()  # (instr_id, day_id, block_index)
    
    # Use stored procedure for optimized query
    room_bookings, instructor_bookings = db_procedures.get_existing_bookings(
        db=db,
        semester=semester,
        years=years,
        exclude_course_id=exclude_course_id
    )
    
    # Build time_label -> block_index mapping if slots_by_day provided
    time_label_to_block_index = {}
    if slots_by_day and day_id_map:
        for day_label, day_slots in slots_by_day.items():
            day_id = day_id_map.get(day_label)
            if day_id is not None:
                for slot in day_slots:
                    time_label_to_block_index[(day_id, slot["label"])] = slot["index"]
    
    # Convert to sets with block_index (canonical numeric indices)
    for booking in room_bookings:
        day_id = booking["day_id"]
        time_label = booking["time_label"]
        if isinstance(time_label, str) and " - " in time_label:
            time_label = time_label.split(" - ", 1)[0].strip()
        
        # Convert time_label to block_index if mapping available
        if time_label_to_block_index:
            block_index = time_label_to_block_index.get((day_id, time_label))
            if block_index is not None:
                booked_room_slots.add((booking["resource_name"], day_id, block_index))
        else:
            # Fallback: use time_label as string (for backward compatibility)
            # This should not happen in normal flow, but kept for safety
            booked_room_slots.add((booking["resource_name"], day_id, time_label))
    
    for booking in instructor_bookings:
        day_id = booking["day_id"]
        time_label = booking["time_label"]
        if isinstance(time_label, str) and " - " in time_label:
            time_label = time_label.split(" - ", 1)[0].strip()
        
        # Convert time_label to block_index if mapping available
        if time_label_to_block_index:
            block_index = time_label_to_block_index.get((day_id, time_label))
            if block_index is not None:
                booked_instr_slots.add((booking["resource_id"], day_id, block_index))
        else:
            # Fallback: use time_label as string (for backward compatibility)
            booked_instr_slots.add((booking["resource_id"], day_id, time_label))
    
    return booked_room_slots, booked_instr_slots


def _retry_unscheduled_subjects(
    db: Session,
    unscheduled_subjects: List[models.Subject],
    course_to_instructors: Dict[str, List[int]],
    course_to_rooms: Dict[str, List[int]],
    slots_by_day: Dict[str, List[Dict]],
    booked_room_slots_global: Set[Tuple[str, int, int]],  # (room_name, day_id, block_index)
    booked_instr_slots_global: Set[Tuple[int, int, int]],  # (instr_id, day_id, block_index)
    rooms: List[models.Room],
    days: List[models.Day],
    room_id_to_name: Dict[int, str],
    course_id: int,
    default_year: Optional[int],
    semester: int,
    focus_subject_ids_set: Optional[Set[int]],
    global_instr_map: Optional[Dict[Tuple[str, int, int], int]] = None,
    scheduled_rows: Optional[List[Dict]] = None,  # CP-scheduled subjects for student conflict checking
    booked_room_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
    booked_instr_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
) -> Dict[int, Dict]:
    """
    Retry pass: attempt to schedule subjects that weren't scheduled in initial cluster runs.
    Uses a simplified greedy approach to find any available slots.
    
    Returns:
        Dict mapping subject_id -> scheduled item dict (one row per subject in retry).
    """
    retry_results: Dict[int, Dict] = {}
    
    if not unscheduled_subjects:
        return retry_results
    
    logger.info("Retry pass: attempting to schedule %d unscheduled subjects", len(unscheduled_subjects))
    
    # Build student time ranges for conflict checking:
    # (course_id, year_level, block_label, day_id) -> [(start_min, end_min), ...]
    # This prevents students in the same course/year/block from having overlapping classes on the same day
    student_time_ranges = defaultdict(list)  # (course_id, year_level, block_label, day_id) -> [(start_min, end_min), ...]
    if scheduled_rows:
        for row in scheduled_rows:
            row_course_id = row.get("course_id", course_id)
            row_year = row.get("year", default_year)
            row_day_id = row.get("day_id")
            start_min = row.get("start_min")
            end_min = row.get("end_min")
            row_block = row.get("block")
            block_key = str(row_block) if row_block is not None else "DEFAULT"
            if row_course_id and row_year is not None and row_day_id and start_min is not None and end_min is not None:
                student_time_ranges[(row_course_id, row_year, block_key, row_day_id)].append((start_min, end_min))

    # Map instructor assignments by (code, course_id, year) so LEC/LAB pairs can reuse them in retry
    lec_instructor_by_key = dict(global_instr_map) if global_instr_map else {}
    if scheduled_rows:
        try:
            scheduled_subject_ids = {row.get("subject_id") for row in scheduled_rows if row.get("subject_id") is not None}
        except Exception:
            scheduled_subject_ids = set()
        scheduled_subjects_lookup = {}
        if scheduled_subject_ids:
            try:
                scheduled_subjects = db.query(models.Subject).filter(models.Subject.id.in_(scheduled_subject_ids)).all()
                scheduled_subjects_lookup = {s.id: s for s in scheduled_subjects}
            except Exception as e:
                logger.warning("Retry pass: could not load scheduled subjects for LEC/LAB instructor reuse: %s", e)
        for row in scheduled_rows:
            sid = row.get("subject_id")
            instr_id = row.get("instructor_id")
            if not sid or not instr_id:
                continue
            subj = scheduled_subjects_lookup.get(sid)
            if not subj:
                continue
            subj_type = (getattr(subj, "type", "") or "").upper().strip()
            if subj_type != "LEC":
                continue
            code = (getattr(subj, "code", "") or "").upper().strip()
            if not code:
                continue
            key_course_id = subj.course_id or course_id
            key_year = subj.year_level or default_year
            key = (code, key_course_id, key_year)
            if key not in lec_instructor_by_key:
                lec_instructor_by_key[key] = instr_id
    
    # Sort unscheduled subjects so LEC sections are processed before LAB sections per code/course/year
    def _retry_sort_key(subj: models.Subject):
        try:
            subj_code = (getattr(subj, "code", "") or "").upper().strip()
            subj_course_key = getattr(subj, "course_id", None) or course_id
            subj_year_key = getattr(subj, "year_level", None) or default_year or 0
            subj_type_val = (getattr(subj, "type", "") or "").upper().strip()
            type_order = 0 if subj_type_val == "LEC" else 1
            return (subj_course_key or 0, subj_year_key, subj_code, type_order, getattr(subj, "id", 0) or 0)
        except Exception:
            # Fallback: keep original order on error
            return (0, 0, "", 1, getattr(subj, "id", 0) or 0)

    try:
        unscheduled_subjects_sorted = sorted(unscheduled_subjects, key=_retry_sort_key)
    except Exception as e:
        logger.warning("Retry pass: could not sort unscheduled subjects by LEC/LAB: %s", e)
        unscheduled_subjects_sorted = unscheduled_subjects

    return _cp_retry_mini_model(
        db=db,
        unscheduled_subjects=unscheduled_subjects_sorted,
        course_to_instructors=course_to_instructors,
        course_to_rooms=course_to_rooms,
        slots_by_day=slots_by_day,
        booked_room_slots_global=booked_room_slots_global,
        booked_instr_slots_global=booked_instr_slots_global,
        rooms=rooms,
        days=days,
        room_id_to_name=room_id_to_name,
        course_id=course_id,
        default_year=default_year,
        semester=semester,
        focus_subject_ids_set=focus_subject_ids_set,
        lec_instructor_by_key=lec_instructor_by_key,
        student_time_ranges=student_time_ranges,
        global_instr_map=global_instr_map,
        booked_room_ranges_global=booked_room_ranges_global,
        booked_instr_ranges_global=booked_instr_ranges_global,
    )

    # Use greedy approach for retry - simpler and faster than full CP model
    for subject in unscheduled_subjects_sorted:
        if focus_subject_ids_set and subject.id not in focus_subject_ids_set:
            continue
            
        # CRITICAL: Maps are now keyed by subject.id, not course_id
        eligible_instrs = course_to_instructors.get(subject.id, [])
        eligible_rooms = course_to_rooms.get(subject.id, [])
        
        if not eligible_instrs or not eligible_rooms:
            continue
        
        subj_type = (getattr(subject, "type", "") or "").upper().strip()
        is_lab_subject = subj_type == "LAB"
        subj_code = (getattr(subject, "code", "") or "").upper().strip()
        subj_course_key = subject.course_id if subject.course_id else course_id
        subj_year_key = subject.year_level if subject.year_level else default_year
        lec_key = (subj_code, subj_course_key, subj_year_key)

        # If we already have a chosen instructor for this code/course/year (from CP or earlier retry), force reuse
        lec_instr_id = lec_instructor_by_key.get(lec_key)
        if lec_instr_id:
            if lec_instr_id in eligible_instrs:
                eligible_instrs = [lec_instr_id]
            else:
                logger.warning(
                    "[RETRY] Subject %s (ID=%s) has mapped LEC/LAB instructor %s not in eligible list %s; skipping retry to keep instructors consistent.",
                    subj_code, subject.id, lec_instr_id, eligible_instrs,
                )
                continue

        rec_slots = subject.recommended_slots or subject.min_slots or 1
        min_slots = subject.min_slots or rec_slots
        if is_lab_subject:
            min_slots = 1
        
        # Try to find any available slot (single-day greedy for both LEC and LAB)
        scheduled = False
        for day in days:
            if scheduled:
                break

            # In retry, LAB subjects now search all days (M/T/W/Th/F), same as LECs.
            # LAB vs LEC separation is enforced via room/instructor/subject type,
            # not by restricting the time grid to Friday only.
            day_slots = slots_by_day.get(day.label, [])
            max_start = len(day_slots) - min_slots
            if max_start < 0:
                continue
            
            for start_pos in range(max_start + 1):
                if scheduled:
                    break
                block = day_slots[start_pos:start_pos + min_slots]
                if len(block) < min_slots:
                    continue
                
                if not is_consecutive_blocks([slot["index"] for slot in block]):
                    continue
                
                # CRITICAL FIX: Check for student conflicts FIRST (before trying rooms/instructors)
                # Student conflicts are time-based, so if this time slot conflicts, ALL rooms/instructors will conflict
                first_slot = block[0]
                last_slot = block[-1]
                subj_course_id = subject.course_id if subject.course_id else course_id
                subj_year = subject.year_level if subject.year_level else default_year
                # Use the subject's student_block (if any) to scope conflicts per block.
                subj_block_index = 1
                try:
                    subj_block_index = getattr(subject, "student_block", 1)
                except Exception:
                    subj_block_index = 1
                try:
                    subj_block_index = int(subj_block_index)
                except (TypeError, ValueError):
                    subj_block_index = 1
                subj_block_label = _block_index_to_label(subj_block_index) or "DEFAULT"
                proposed_start_min = first_slot["start_min"]
                proposed_end_min = last_slot["end_min"]

                # Range-based conflicts (handles overlapping TIME_BLOCK definitions)
                if booked_room_ranges_global is not None or booked_instr_ranges_global is not None:
                    # We only know the day here; room/instructor are checked in their loops below.
                    pass
                
                # Check if this time slot would conflict with any already-scheduled subject for same students
                has_student_conflict = False
                existing_ranges = student_time_ranges.get((subj_course_id, subj_year, subj_block_label, day.id), [])
                for existing_start, existing_end in existing_ranges:
                    # Check for overlap: proposed time overlaps with existing time
                    if not (proposed_end_min <= existing_start or proposed_start_min >= existing_end):
                        has_student_conflict = True
                        # Only log once per start_pos to avoid spam
                        if start_pos == 0 or start_pos % 10 == 0:  # Log every 10th attempt or first attempt
                            logger.debug(f"[RETRY] Subject {subject.id} ({subject.code}) time slot "
                                           f"{proposed_start_min}-{proposed_end_min} conflicts with "
                                           f"{existing_start}-{existing_end} (course_id={subj_course_id}, year={subj_year}, day={day.id})")
                        break

                # If this time slot has a student conflict, skip ALL rooms/instructors for this start_pos
                # and try the next start position
                if has_student_conflict:
                    continue  # Skip to next start_pos (student conflicts are time-based, not room/instructor-based)
                
                # Check room availability
                for room_id in eligible_rooms:
                    if scheduled:
                        break
                    room_name = room_id_to_name.get(room_id)
                    if not room_name:
                        continue

                    # Range-based room conflict check (cross-block safety)
                    if booked_room_ranges_global is not None and _range_conflicts(
                        booked_room_ranges_global, room_name, day.id, proposed_start_min, proposed_end_min
                    ):
                        continue
                    
                    # Check if room is booked for any slot in block (using block_index)
                    room_available = True
                    for slot in block:
                        block_index = slot["index"]
                        if (room_name, day.id, block_index) in booked_room_slots_global:
                            room_available = False
                            break
                    
                    if not room_available:
                        continue
                    
                    # Check instructor availability (using block_index)
                    for instructor_id in eligible_instrs:
                        if scheduled:
                            break

                        # Range-based instructor conflict check (cross-block safety)
                        if booked_instr_ranges_global is not None and _range_conflicts(
                            booked_instr_ranges_global, instructor_id, day.id, proposed_start_min, proposed_end_min
                        ):
                            continue
                        instr_available = True
                        for slot in block:
                            block_index = slot["index"]
                            if (instructor_id, day.id, block_index) in booked_instr_slots_global:
                                instr_available = False
                                break
                        
                        if instr_available:
                            time_label = first_slot["label"] if min_slots == 1 else f"{first_slot['start']}–{last_slot['end']}"

                            # Map back to original subject ID for external consumers.
                            orig_id_val = getattr(subject, "original_subject_id", getattr(subject, "id", None))
                            try:
                                orig_subject_id = int(orig_id_val) if orig_id_val is not None else None
                            except Exception:
                                orig_subject_id = None
                            if orig_subject_id is None:
                                orig_subject_id = int(subject.id)

                            retry_results[subject.id] = {
                                # External subject identifier: original DB subject ID
                                "subject_id": orig_subject_id,
                                # Internal clone identifier (per-block synthetic ID) for bookkeeping
                                "clone_subject_id": subject.id,
                                "course_id": subj_course_id,
                                "instructor_id": instructor_id,
                                "room_id": room_id,
                                "day_id": day.id,
                                "time": time_label,
                                "year": subj_year,
                                "semester": subject.semester if subject.semester else semester,
                                "block": subj_block_label,
                                "start_min": proposed_start_min,
                                "end_min": proposed_end_min,
                            }

                            if subj_code:
                                map_key = (subj_code, subj_course_key, subj_year_key)
                                if map_key not in lec_instructor_by_key:
                                    lec_instructor_by_key[map_key] = instructor_id
                                    if global_instr_map is not None:
                                        try:
                                            gkey = (subj_code, int(subj_course_key), int(subj_year_key) if subj_year_key is not None else int(default_year))
                                        except (TypeError, ValueError):
                                            gkey = None
                                        if gkey is not None and gkey not in global_instr_map:
                                            global_instr_map[gkey] = instructor_id

                            for slot in block:
                                block_index = slot["index"]
                                booked_room_slots_global.add((room_name, day.id, block_index))
                                booked_instr_slots_global.add((instructor_id, day.id, block_index))

                            if booked_room_ranges_global is not None:
                                booked_room_ranges_global[(room_name, int(day.id))].append((int(proposed_start_min), int(proposed_end_min)))
                            if booked_instr_ranges_global is not None:
                                booked_instr_ranges_global[(int(instructor_id), int(day.id))].append((int(proposed_start_min), int(proposed_end_min)))

                            student_time_ranges[(subj_course_id, subj_year, subj_block_label, day.id)].append((proposed_start_min, proposed_end_min))

                            scheduled = True
                            break
    
    logger.info("Retry pass completed: scheduled %d/%d subjects", len(retry_results), len(unscheduled_subjects))
    return retry_results


def _cp_retry_mini_model(
    db: Session,
    unscheduled_subjects: List[models.Subject],
    course_to_instructors: Dict[str, List[int]],
    course_to_rooms: Dict[str, List[int]],
    slots_by_day: Dict[str, List[Dict]],
    booked_room_slots_global: Set[Tuple[str, int, int]],
    booked_instr_slots_global: Set[Tuple[int, int, int]],
    rooms: List[models.Room],
    days: List[models.Day],
    room_id_to_name: Dict[int, str],
    course_id: int,
    default_year: Optional[int],
    semester: int,
    focus_subject_ids_set: Optional[Set[int]],
    lec_instructor_by_key: Dict[Tuple[str, int, int], int],
    student_time_ranges: Dict[Tuple[int, int, str, int], List[Tuple[int, int]]],
    global_instr_map: Optional[Dict[Tuple[str, int, int], int]] = None,
    booked_room_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
    booked_instr_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
) -> Dict[int, Dict]:
    retry_results: Dict[int, Dict] = {}

    if not unscheduled_subjects:
        return retry_results

    logger.info(
        "CP retry pass: attempting to schedule %d unscheduled subjects with mini CP model",
        len(unscheduled_subjects),
    )

    debug_subject_stats: Dict[int, Dict[str, int]] = defaultdict(
        lambda: {
            "eligible_instrs": 0,
            "eligible_rooms": 0,
            "windows_considered": 0,
            "windows_student_conflict": 0,
            "room_checks": 0,
            "room_conflicts": 0,
            "instr_checks": 0,
            "instr_conflicts": 0,
            "candidates": 0,
        }
    )

    candidates: List[Dict[str, Any]] = []

    for subject in unscheduled_subjects:
        # IMPORTANT: When block_count > 1, subjects are per-block clones. Use original_subject_id
        # for focus filtering so that cloned IDs are not accidentally skipped.
        raw_id = getattr(subject, "id", None)
        try:
            clone_id = int(raw_id) if raw_id is not None else None
        except Exception:
            clone_id = raw_id

        base_id_val = getattr(subject, "original_subject_id", clone_id)
        try:
            base_id = int(base_id_val) if base_id_val is not None else clone_id
        except Exception:
            base_id = clone_id

        if focus_subject_ids_set and (base_id is None or base_id not in focus_subject_ids_set):
            continue

        stats = debug_subject_stats[clone_id]

        subj_type = (getattr(subject, "type", "") or "").upper().strip()
        is_lec_subject = subj_type == "LEC"
        is_lab_subject = subj_type == "LAB"
        
        # LEC subjects can now retry with MW/TTh patterns
        # LAB subjects retry with Friday single-day pattern
        
        subj_code = (getattr(subject, "code", "") or "").upper().strip()
        subj_course_key = subject.course_id if subject.course_id else course_id
        subj_year_key = subject.year_level if subject.year_level else default_year
        lec_key = (subj_code, subj_course_key, subj_year_key)

        # Primary path for retry: always derive eligibility from DB stored procedures when available.
        eligible_instrs: List[int] = []
        eligible_rooms: List[int] = []

        if db is not None:
            try:
                base_sid_val = getattr(subject, "original_subject_id", subject.id)
                base_sid = int(base_sid_val) if base_sid_val is not None else int(subject.id)
            except Exception:
                try:
                    base_sid = int(subject.id)
                except Exception:
                    base_sid = None

            if base_sid is not None:
                try:
                    db_instrs = db_procedures.get_instructor_eligibility(db, base_sid)
                    if db_instrs:
                        eligible_instrs = [inst.id for inst in db_instrs]
                    logger.info(
                        "CP retry SP debug: subject %s (sid=%s, base_sid=%s) instr_count=%d",
                        subj_code or "?",
                        getattr(subject, "id", None),
                        base_sid,
                        len(db_instrs) if db_instrs is not None else 0,
                    )
                except Exception as e:
                    logger.warning(
                        "CP retry: instructor eligibility SP failed for subject %s (ID=%s, base_sid=%s): %s",
                        subj_code or "?",
                        subject.id,
                        base_sid,
                        e,
                    )

                try:
                    db_rooms = db_procedures.get_room_eligibility(db, base_sid)
                    if db_rooms:
                        eligible_rooms = [room.id for room in db_rooms]
                    logger.info(
                        "CP retry SP debug: subject %s (sid=%s, base_sid=%s) room_count=%d",
                        subj_code or "?",
                        getattr(subject, "id", None),
                        base_sid,
                        len(db_rooms) if db_rooms is not None else 0,
                    )
                except Exception as e:
                    logger.warning(
                        "CP retry: room eligibility SP failed for subject %s (ID=%s, base_sid=%s): %s",
                        subj_code or "?",
                        subject.id,
                        base_sid,
                        e,
                    )

        # Fallback only if DB is not available or SP returned nothing
        if not eligible_instrs:
            eligible_instrs = course_to_instructors.get(subject.id, []) or []
        if not eligible_rooms:
            eligible_rooms = course_to_rooms.get(subject.id, []) or []

        # CRITICAL: Exclude FIELD room for non-NSTP subjects in retry pass
        # FIELD is reserved exclusively for NSTP subjects
        if not _is_nstp_subject(subject):
            field_room_ids = [room.id for room in rooms if (room.name or "").upper() == "FIELD"]
            if field_room_ids:
                eligible_rooms = [rid for rid in eligible_rooms if rid not in field_room_ids]

        stats["eligible_instrs"] = len(eligible_instrs)
        stats["eligible_rooms"] = len(eligible_rooms)

        if not eligible_instrs or not eligible_rooms:
            logger.info(
                "CP retry debug: subject %s (ID=%s) has no eligible %s during retry",
                subj_code or "?",
                subject.id,
                "instructors" if not eligible_instrs else "rooms",
            )
            continue

        lec_instr_id = None
        student_block_index = 1
        try:
            student_block_index = getattr(subject, "student_block", 1)
        except Exception:
            student_block_index = 1
        try:
            student_block_index = int(student_block_index)
        except (TypeError, ValueError):
            student_block_index = 1

        if student_block_index == 1:
            lec_instr_id = lec_instructor_by_key.get(lec_key)
        if lec_instr_id:
            if lec_instr_id in eligible_instrs:
                eligible_instrs = [lec_instr_id]
            else:
                logger.info(
                    "CP retry debug: subject %s (ID=%s) LEC/LAB instructor %s not in eligible list %s; skipping",
                    subj_code or "?",
                    subject.id,
                    lec_instr_id,
                    eligible_instrs,
                )
                continue

        rec_slots = subject.recommended_slots or subject.min_slots or 1
        min_slots = subject.min_slots or rec_slots
        if is_lab_subject:
            min_slots = 1

        # Define day patterns for retry
        # LAB: Friday only (single day), Saturday as emergency
        # LEC: MW or TTh patterns (paired days), Friday as fallback, Saturday as emergency
        if is_lec_subject:
            # For LEC, try MW, TTh, Friday patterns first, then Saturday as last resort
            day_patterns = [
                ("M", "W"),   # Monday + Wednesday
                ("T", "TH"),  # Tuesday + Thursday
                ("F",),       # Friday (3-hour single day) - fallback
                ("SAT",),     # Saturday - EMERGENCY ONLY
            ]
        else:
            # For LAB (and other types), try Friday first, then Saturday
            day_patterns = [
                ("F",),       # Friday - primary
                ("SAT",),     # Saturday - EMERGENCY ONLY
            ]
        
        for pattern in day_patterns:
            # Get day objects for this pattern
            pattern_days = [d for d in days if d.label in pattern]
            if len(pattern_days) != len(pattern):
                logger.debug(f"CP retry: subject {subject.id} pattern {pattern} skipped - missing days")
                continue  # Skip if not all days in pattern exist
            
            # For paired patterns, ensure we have all required days
            # Skip only if the pattern requires multiple days but we don't have them all
            if len(pattern) > 1 and len(pattern_days) < len(pattern):
                logger.debug(f"CP retry: subject {subject.id} pattern {pattern} skipped - need {len(pattern)} days, have {len(pattern_days)}")
                continue  # Skip if we don't have all days for a multi-day pattern
            
            # For single-day patterns (LAB), just use the first day
            primary_day = pattern_days[0]
            day_slots = slots_by_day.get(primary_day.label, [])
            max_start = len(day_slots) - min_slots
            
            # Debug: Log available slots for this pattern
            if subj_code in ("GE - E", "GE - CW"):
                logger.info(f"CP retry DEBUG: subject {subj_code} (ID={subject.id}) pattern={pattern}, day_slots={len(day_slots)}, min_slots={min_slots}, max_start={max_start}")
            
            if max_start < 0:
                if subj_code in ("GE - E", "GE - CW"):
                    logger.info(f"CP retry DEBUG: subject {subj_code} pattern={pattern} skipped - max_start < 0")
                continue

            for start_pos in range(max_start + 1):
                block = day_slots[start_pos : start_pos + min_slots]
                if len(block) < min_slots:
                    continue

                if not is_consecutive_blocks([slot["index"] for slot in block]):
                    continue

                stats["windows_considered"] += 1

                first_slot = block[0]
                last_slot = block[-1]
                subj_course_id = subject.course_id if subject.course_id else course_id
                subj_year = subject.year_level if subject.year_level else default_year

                subj_block_index = 1
                try:
                    subj_block_index = getattr(subject, "student_block", 1)
                except Exception:
                    subj_block_index = 1
                try:
                    subj_block_index = int(subj_block_index)
                except (TypeError, ValueError):
                    subj_block_index = 1
                subj_block_label = _block_index_to_label(subj_block_index) or "DEFAULT"

                proposed_start_min = first_slot["start_min"]
                proposed_end_min = last_slot["end_min"]

                # Check student conflicts for ALL days in the pattern
                has_student_conflict = False
                conflict_detail = None
                for check_day in pattern_days:
                    existing_ranges = student_time_ranges.get(
                        (subj_course_id, subj_year, subj_block_label, check_day.id), []
                    )
                    for existing_start, existing_end in existing_ranges:
                        if not (
                            proposed_end_min <= existing_start
                            or proposed_start_min >= existing_end
                        ):
                            has_student_conflict = True
                            conflict_detail = f"day={check_day.label} proposed={proposed_start_min}-{proposed_end_min} conflicts with existing={existing_start}-{existing_end}"
                            break
                    if has_student_conflict:
                        break

                if has_student_conflict:
                    stats["windows_student_conflict"] += 1
                    if subj_code in ("GE - E", "GE - CW"):
                        logger.info(f"CP retry DEBUG: subject {subj_code} pattern={pattern} pos={start_pos} STUDENT CONFLICT: {conflict_detail}")
                    continue
                
                # Log viable windows for GE-E/GE-CW
                if subj_code in ("GE - E", "GE - CW"):
                    logger.info(f"CP retry DEBUG: subject {subj_code} pattern={pattern} pos={start_pos} time={proposed_start_min}-{proposed_end_min} - VIABLE WINDOW, checking rooms/instructors")

                for room_id in eligible_rooms:
                    room_name = room_id_to_name.get(room_id)
                    if not room_name:
                        continue

                    stats["room_checks"] += 1

                    # Check room availability for ALL days in the pattern
                    room_available = True
                    for check_day in pattern_days:
                        check_day_slots = slots_by_day.get(check_day.label, [])
                        if start_pos < len(check_day_slots):
                            check_block = check_day_slots[start_pos : start_pos + min_slots]
                            for slot in check_block:
                                block_index = slot["index"]
                                if (room_name, check_day.id, block_index) in booked_room_slots_global:
                                    room_available = False
                                    break
                        if not room_available:
                            break

                    if not room_available:
                        stats["room_conflicts"] += 1
                        continue

                    for instructor_id in eligible_instrs:
                        stats["instr_checks"] += 1
                        
                        # Check instructor availability for ALL days in the pattern
                        instr_available = True
                        for check_day in pattern_days:
                            check_day_slots = slots_by_day.get(check_day.label, [])
                            if start_pos < len(check_day_slots):
                                check_block = check_day_slots[start_pos : start_pos + min_slots]
                                for slot in check_block:
                                    block_index = slot["index"]
                                    if (
                                        instructor_id,
                                        check_day.id,
                                        block_index,
                                    ) in booked_instr_slots_global:
                                        instr_available = False
                                        break
                            if not instr_available:
                                break

                        if not instr_available:
                            stats["instr_conflicts"] += 1
                            continue

                        time_label = (
                            first_slot["label"]
                            if min_slots == 1
                            else f"{first_slot['start']}–{last_slot['end']}"
                        )
                        
                        # For LEC (MW/TTh), create a SINGLE unified candidate representing BOTH days
                        # For LAB (F), create a single-day candidate
                        if is_lec_subject and len(pattern_days) == 2:
                            # Build paired candidate with both days' info
                            paired_days_info = []
                            valid_pair = True
                            for pattern_day in pattern_days:
                                pattern_day_slots = slots_by_day.get(pattern_day.label, [])
                                if start_pos >= len(pattern_day_slots):
                                    valid_pair = False
                                    break
                                pattern_block = pattern_day_slots[start_pos : start_pos + min_slots]
                                if len(pattern_block) < min_slots:
                                    valid_pair = False
                                    break
                                
                                pattern_first_slot = pattern_block[0]
                                pattern_last_slot = pattern_block[-1]
                                paired_days_info.append({
                                    "day_id": pattern_day.id,
                                    "day_label": pattern_day.label,
                                    "slots": pattern_block,
                                    "start_min": pattern_first_slot["start_min"],
                                    "end_min": pattern_last_slot["end_min"],
                                    "time_label": f"{pattern_first_slot['start']}–{pattern_last_slot['end']}",
                                })
                            
                            if not valid_pair:
                                continue
                            
                            # Create ONE candidate representing both days together
                            candidates.append({
                                "subject": subject,
                                "subject_id": subject.id,
                                "course_id": subj_course_id,
                                "year": subj_year,
                                "student_block_label": subj_block_label,
                                "subj_code": subj_code,
                                "subj_course_key": subj_course_key,
                                "subj_year_key": subj_year_key,
                                "lec_key": lec_key,
                                "room_id": room_id,
                                "room_name": room_name,
                                "instructor_id": instructor_id,
                                "pattern": pattern,
                                "start_pos": start_pos,
                                "is_paired": True,  # Mark as paired LEC candidate
                                "paired_days": paired_days_info,  # Both days' info
                                # Use first day's info for backward compatibility
                                "day_id": paired_days_info[0]["day_id"],
                                "slots": paired_days_info[0]["slots"],
                                "start_min": paired_days_info[0]["start_min"],
                                "end_min": paired_days_info[0]["end_min"],
                                "time_label": paired_days_info[0]["time_label"],
                                "student_key": (subj_course_id, subj_year, subj_block_label, paired_days_info[0]["day_id"]),
                            })
                            stats["candidates"] += 1
                        else:
                            # Single-day candidate (LAB Friday)
                            pattern_day = pattern_days[0]
                            pattern_day_slots = slots_by_day.get(pattern_day.label, [])
                            if start_pos >= len(pattern_day_slots):
                                continue
                            pattern_block = pattern_day_slots[start_pos : start_pos + min_slots]
                            if len(pattern_block) < min_slots:
                                continue
                            
                            pattern_first_slot = pattern_block[0]
                            pattern_last_slot = pattern_block[-1]
                            pattern_time_label = (
                                pattern_first_slot["label"]
                                if min_slots == 1
                                else f"{pattern_first_slot['start']}–{pattern_last_slot['end']}"
                            )
                            
                            student_key = (
                                subj_course_id,
                                subj_year,
                                subj_block_label,
                                pattern_day.id,
                            )

                            candidates.append({
                                "subject": subject,
                                "subject_id": subject.id,
                                "course_id": subj_course_id,
                                "year": subj_year,
                                "student_block_label": subj_block_label,
                                "subj_code": subj_code,
                                "subj_course_key": subj_course_key,
                                "subj_year_key": subj_year_key,
                                "lec_key": lec_key,
                                "day_id": pattern_day.id,
                                "room_id": room_id,
                                "room_name": room_name,
                                "instructor_id": instructor_id,
                                "slots": pattern_block,
                                "start_min": pattern_first_slot["start_min"],
                                "end_min": pattern_last_slot["end_min"],
                                "time_label": pattern_time_label,
                                "student_key": student_key,
                                "pattern": pattern,
                                "start_pos": start_pos,
                                "is_paired": False,
                            })
                            stats["candidates"] += 1

    per_subject_candidate_counts: Dict[int, int] = defaultdict(int)
    for cand in candidates:
        try:
            sid_val = int(cand["subject_id"])
        except Exception:
            continue
        per_subject_candidate_counts[sid_val] += 1

    for subject in unscheduled_subjects:
        sid = getattr(subject, "id", None)
        subj_code = (getattr(subject, "code", "") or "").upper().strip()
        stats = debug_subject_stats.get(sid, {})
        logger.info(
            "CP retry debug summary: subject %s (ID=%s): candidates=%d, eligible_instrs=%d, eligible_rooms=%d, "
            "windows_considered=%d, windows_student_conflict=%d, room_checks=%d, room_conflicts=%d, "
            "instr_checks=%d, instr_conflicts=%d",
            subj_code or "?",
            sid,
            per_subject_candidate_counts.get(sid, 0),
            stats.get("eligible_instrs", 0),
            stats.get("eligible_rooms", 0),
            stats.get("windows_considered", 0),
            stats.get("windows_student_conflict", 0),
            stats.get("room_checks", 0),
            stats.get("room_conflicts", 0),
            stats.get("instr_checks", 0),
            stats.get("instr_conflicts", 0),
        )

    if not candidates:
        logger.info(
            "CP retry pass: no viable candidate assignments for %d unscheduled subjects",
            len(unscheduled_subjects),
        )
        return retry_results

    logger.info(
        "CP retry pass: built %d candidate assignments for %d unscheduled subjects",
        len(candidates),
        len(unscheduled_subjects),
    )

    model = cp_model.CpModel()
    vars_list: List[cp_model.IntVar] = []

    for idx, cand in enumerate(candidates):
        var = model.NewBoolVar(
            f"retry_s{cand['subject_id']}_d{cand['day_id']}_r{cand['room_id']}_i{cand['instructor_id']}_{idx}"
        )
        vars_list.append(var)

    subject_to_indices: Dict[int, List[int]] = defaultdict(list)
    for idx, cand in enumerate(candidates):
        subject_to_indices[int(cand["subject_id"])] .append(idx)

    for subject_id, indices in subject_to_indices.items():
        model.Add(sum(vars_list[i] for i in indices) <= 1)

    room_slot_to_indices: Dict[Tuple[str, int, int], List[int]] = defaultdict(list)
    instr_slot_to_indices: Dict[Tuple[int, int, int], List[int]] = defaultdict(list)
    student_slot_to_indices: Dict[Tuple[int, int, str, int, int], List[int]] = defaultdict(list)

    for idx, cand in enumerate(candidates):
        day_id = int(cand["day_id"])
        room_name = cand["room_name"]
        instructor_id = int(cand["instructor_id"])
        course_key, year_key, block_label, _day_id = cand["student_key"]
        for slot in cand["slots"]:
            block_index = slot["index"]
            room_slot_to_indices[(room_name, day_id, block_index)].append(idx)
            instr_slot_to_indices[(instructor_id, day_id, block_index)].append(idx)
            student_slot_to_indices[(course_key, year_key, block_label, day_id, block_index)].append(idx)

    for indices in room_slot_to_indices.values():
        if len(indices) > 1:
            model.Add(sum(vars_list[i] for i in indices) <= 1)

    for indices in instr_slot_to_indices.values():
        if len(indices) > 1:
            model.Add(sum(vars_list[i] for i in indices) <= 1)

    for indices in student_slot_to_indices.values():
        if len(indices) > 1:
            model.Add(sum(vars_list[i] for i in indices) <= 1)

    lec_key_to_instrs: Dict[Tuple[str, int, int], Set[int]] = defaultdict(set)
    for idx, cand in enumerate(candidates):
        lec_key = cand.get("lec_key")
        if not lec_key:
            continue
        if lec_key in lec_instructor_by_key:
            continue
        try:
            instr_id_val = int(cand["instructor_id"])
        except Exception:
            continue
        lec_key_to_instrs[lec_key].add(instr_id_val)

    lec_key_choice_bools: Dict[Tuple[Tuple[str, int, int], int], cp_model.IntVar] = {}
    for lec_key, instr_ids in lec_key_to_instrs.items():
        if len(instr_ids) <= 1:
            continue
        choice_vars = []
        code_val, course_val, year_val = lec_key
        try:
            code_str = "".join(ch if ch.isalnum() else "_" for ch in str(code_val))
        except Exception:
            code_str = "CODE"
        for instr_id_val in instr_ids:
            bool_var = model.NewBoolVar(
                f"retry_lecgrp_{code_str}_{course_val}_{year_val}_i{instr_id_val}"
            )
            lec_key_choice_bools[(lec_key, instr_id_val)] = bool_var
            choice_vars.append(bool_var)
        model.Add(sum(choice_vars) == 1)

    for idx, cand in enumerate(candidates):
        lec_key = cand.get("lec_key")
        if not lec_key:
            continue
        if lec_key in lec_instructor_by_key:
            continue
        try:
            instr_id_val = int(cand["instructor_id"])
        except Exception:
            continue
        key = (lec_key, instr_id_val)
        bool_var = lec_key_choice_bools.get(key)
        if bool_var is not None:
            model.Add(vars_list[idx] <= bool_var)

    model.Maximize(sum(vars_list))

    solver = cp_model.CpSolver()
    # OPTIMIZED: Same fast settings as main solver
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = max(1, min(2, os.cpu_count() or 1))
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.linearization_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.relative_gap_limit = 0.05
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)
    logger.info("CP retry solver status: %s", solver.StatusName(status))

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return retry_results

    scheduled_subject_ids = set()  # Track which subjects got scheduled
    
    for idx, var in enumerate(vars_list):
        if not solver.BooleanValue(var):
            continue

        cand = candidates[idx]
        subject = cand["subject"]
        subj_code = cand["subj_code"]
        subj_course_key = cand["subj_course_key"]
        subj_year_key = cand["subj_year_key"]
        subj_course_id = cand["course_id"]
        subj_year = cand["year"]
        subj_block_label = cand["student_key"][2]
        room_id = cand["room_id"]
        room_name = cand["room_name"]
        instructor_id = cand["instructor_id"]

        orig_id_val = getattr(
            subject,
            "original_subject_id",
            getattr(subject, "id", None),
        )
        try:
            orig_subject_id = int(orig_id_val) if orig_id_val is not None else None
        except Exception:
            orig_subject_id = None
        if orig_subject_id is None:
            orig_subject_id = int(subject.id)

        # Handle paired LEC candidates (MW or TTh) - create results for BOTH days
        if cand.get("is_paired") and cand.get("paired_days"):
            # Store list of results for this subject (multiple days)
            paired_results = []
            for day_info in cand["paired_days"]:
                paired_results.append({
                    "subject_id": orig_subject_id,
                    "clone_subject_id": subject.id,
                    "course_id": subj_course_id,
                    "instructor_id": instructor_id,
                    "room_id": room_id,
                    "day_id": day_info["day_id"],
                    "time": day_info["time_label"],
                    "year": subj_year,
                    "semester": subject.semester if subject.semester else semester,
                    "block": subj_block_label,
                    "start_min": day_info["start_min"],
                    "end_min": day_info["end_min"],
                })
            # Store the paired results (multiple items for this subject)
            retry_results[subject.id] = paired_results
            scheduled_subject_ids.add(subject.id)
        else:
            # Single-day candidate (LAB Friday)
            day_id = cand["day_id"]
            start_min = cand["start_min"]
            end_min = cand["end_min"]
            time_label = cand["time_label"]
            
            retry_results[subject.id] = {
                "subject_id": orig_subject_id,
                "clone_subject_id": subject.id,
                "course_id": subj_course_id,
                "instructor_id": instructor_id,
                "room_id": room_id,
                "day_id": day_id,
                "time": time_label,
                "year": subj_year,
                "semester": subject.semester if subject.semester else semester,
                "block": subj_block_label,
                "start_min": start_min,
                "end_min": end_min,
            }

        if subj_code:
            map_key = (subj_code, subj_course_key, subj_year_key)
            if map_key not in lec_instructor_by_key:
                lec_instructor_by_key[map_key] = instructor_id
                if global_instr_map is not None:
                    try:
                        gkey = (
                            subj_code,
                            int(subj_course_key),
                            int(subj_year_key)
                            if subj_year_key is not None
                            else int(default_year),
                        )
                    except (TypeError, ValueError):
                        gkey = None
                    if gkey is not None and gkey not in global_instr_map:
                        global_instr_map[gkey] = instructor_id

        # Book slots for ALL days (handle both paired and single-day candidates)
        if cand.get("is_paired") and cand.get("paired_days"):
            for day_info in cand["paired_days"]:
                for slot in day_info["slots"]:
                    block_index = slot["index"]
                    booked_room_slots_global.add((room_name, day_info["day_id"], block_index))
                    booked_instr_slots_global.add((instructor_id, day_info["day_id"], block_index))
                student_time_ranges[(subj_course_id, subj_year, subj_block_label, day_info["day_id"])].append(
                    (day_info["start_min"], day_info["end_min"])
                )
        else:
            for slot in cand["slots"]:
                block_index = slot["index"]
                booked_room_slots_global.add((room_name, day_id, block_index))
                booked_instr_slots_global.add((instructor_id, day_id, block_index))
            student_time_ranges[cand["student_key"]].append((start_min, end_min))

    logger.info(
        "CP retry pass completed: scheduled %d/%d subjects",
        len(retry_results),
        len(unscheduled_subjects),
    )
    return retry_results

def greedy_initial_schedule(
    cluster_subjects: List[models.Subject],
    course_to_instructors: Dict[str, List[int]],
    course_to_rooms: Dict[str, List[int]],
    slots_by_day: Dict[str, List[Dict]],
    booked_room_slots: Set[Tuple[str, int, int]],  # (room_name, day_id, block_index)
    booked_instr_slots: Set[Tuple[int, int, int]],  # (instr_id, day_id, block_index)
    rooms: List[models.Room],
    days: List[models.Day]
) -> Dict:
    """
    Greedy initializer (warm-start) - simple first-fit greedy scheduling
    
    Returns:
        hints dict: map key (subject_id, room_id, slot_start, instructor_id, dur) -> 0/1
    """
    hints = {}
    room_id_to_name = {r.id: r.name for r in rooms}
    
    for subject in cluster_subjects:
        course_id = subject.course_id
        rec_slots = subject.recommended_slots or subject.min_slots or 1
        eligible_instrs = course_to_instructors.get(course_id, []) if course_id else []
        eligible_rooms = course_to_rooms.get(course_id, []) if course_id else []
        
        scheduled_flag = False
        
        # Simple loop: days -> start -> room -> instructor
        for day in days:
            if scheduled_flag:
                break
            day_label = day.label
            day_slots = slots_by_day.get(day_label, [])
            max_start = len(day_slots) - rec_slots
            if max_start < 0:
                continue
            
            for start_pos in range(max_start + 1):
                if scheduled_flag:
                    break
                block = day_slots[start_pos:start_pos + rec_slots]
                if not block or len(block) < rec_slots:
                    continue
                
                # Check if blocks are consecutive using helper function
                if not is_consecutive_blocks([slot["index"] for slot in block]):
                    continue
                
                global_start = block[0]["index"]
                
                for room_id in eligible_rooms:
                    if scheduled_flag:
                        break
                    room_name = room_id_to_name.get(room_id)
                    if room_name is None:
                        continue
                    
                    # Check booked_room_slots (using block_index)
                    if any((room_name, day.id, slot["index"]) in booked_room_slots for slot in block):
                        continue
                    
                    for instructor_id in eligible_instrs:
                        # Check booked_instr_slots (using block_index)
                        if any((instructor_id, day.id, slot["index"]) in booked_instr_slots for slot in block):
                            continue
                        
                        # Accept this as greedy hint
                        hints[(subject.id, room_id, global_start, instructor_id, rec_slots)] = 1
                        
                        # Mark booked (using block_index)
                        for slot in block:
                            booked_room_slots.add((room_name, day.id, slot["index"]))
                            booked_instr_slots.add((instructor_id, day.id, slot["index"]))
                        
                        scheduled_flag = True
                        break
    
    return hints


def _generate_fallback_time_windows(
    subject: Any,
    slots_by_day: Dict[str, List[Dict[str, Any]]],
    days: List,
    logger: Any,
) -> List[Dict[str, Any]]:
    """
    Generate fallback time windows for a subject when no valid options exist.
    This is a last resort to ensure subjects can be scheduled.
    
    Args:
        subject: The subject to schedule
        slots_by_day: Available time slots by day
        days: List of day objects
        logger: Logger for debug output
    
    Returns:
        List of basic scheduling options
    """
    options = []
    
    # Short day names
    MON, TUE, WED, THU, FRI = "M", "T", "W", "TH", "F"
    
    # Get subject type
    if hasattr(subject, "type"):
        subj_type = str(subject.type).upper().strip()
    elif isinstance(subject, dict):
        subj_type = str(subject.get("type", "")).upper().strip()
    else:
        subj_type = ""
    
    # Get subject ID
    subj_id = getattr(subject, "id", "?")
    
    # Day label to day object mapping
    day_label_to_day = {d.label: d for d in days}
    
    logger.warning(f"[FALLBACK] Generating time windows for subject {subj_id} type {subj_type}")
    
    # For LEC subjects, generate MW and TTh patterns only (no Friday)
    if subj_type == "LEC":
        # MW pattern
        if MON in slots_by_day and WED in slots_by_day:
            for mon_slot in slots_by_day[MON][:3]:  # Limit to first 3 slots
                wed_slot = _find_matching_slot(slots_by_day[WED], mon_slot)
                if wed_slot is None:
                    continue
                    
                mon_day = day_label_to_day.get(MON)
                wed_day = day_label_to_day.get(WED)
                
                start_min = mon_slot.get("start_min")
                end_min = mon_slot.get("end_min")
                duration_min = end_min - start_min
                
                options.append({
                    "days": [MON, WED],
                    "day_ids": [mon_day.id, wed_day.id],
                    "day_id": mon_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": {mon_slot.get("index", 0), wed_slot.get("index", 0)},
                    "blocks_by_day": {mon_day.id: {mon_slot.get("index", 0)}, wed_day.id: {wed_slot.get("index", 0)}},
                    "slot_indexes": [mon_slot.get("index", 0), wed_slot.get("index", 0)],
                    "blocks_spanned": set(),
                    "slot_labels": [mon_slot.get("label", ""), wed_slot.get("label", "")],
                    "num_slots": 2,
                })
        
        # TTh pattern
        if TUE in slots_by_day and THU in slots_by_day:
            for tue_slot in slots_by_day[TUE][:3]:  # Limit to first 3 slots
                thu_slot = _find_matching_slot(slots_by_day[THU], tue_slot)
                if thu_slot is None:
                    continue
                    
                tue_day = day_label_to_day.get(TUE)
                thu_day = day_label_to_day.get(THU)
                
                start_min = tue_slot.get("start_min")
                end_min = tue_slot.get("end_min")
                duration_min = end_min - start_min
                
                options.append({
                    "days": [TUE, THU],
                    "day_ids": [tue_day.id, thu_day.id],
                    "day_id": tue_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": {tue_slot.get("index", 0), thu_slot.get("index", 0)},
                    "blocks_by_day": {tue_day.id: {tue_slot.get("index", 0)}, thu_day.id: {thu_slot.get("index", 0)}},
                    "slot_indexes": [tue_slot.get("index", 0), thu_slot.get("index", 0)],
                    "blocks_spanned": set(),
                    "slot_labels": [tue_slot.get("label", ""), thu_slot.get("label", "")],
                    "num_slots": 2,
                })
    
    # For LAB subjects, generate single-day patterns on any available day
    else:
        if MON in slots_by_day and WED in slots_by_day:
            for mon_slot in slots_by_day[MON][:3]:
                wed_slot = _find_matching_slot(slots_by_day[WED], mon_slot)
                if wed_slot is None:
                    continue

                mon_day = day_label_to_day.get(MON)
                wed_day = day_label_to_day.get(WED)
                if not mon_day or not wed_day:
                    continue

                start_min = mon_slot.get("start_min")
                end_min = mon_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [MON, WED],
                    "day_ids": [mon_day.id, wed_day.id],
                    "day_id": mon_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": {mon_slot.get("index", 0), wed_slot.get("index", 0)},
                    "blocks_by_day": {mon_day.id: {mon_slot.get("index", 0)}, wed_day.id: {wed_slot.get("index", 0)}},
                    "slot_indexes": [mon_slot.get("index", 0), wed_slot.get("index", 0)],
                    "blocks_spanned": set(),
                    "slot_labels": [mon_slot.get("label", ""), wed_slot.get("label", "")],
                    "num_slots": 2,
                })

        if TUE in slots_by_day and THU in slots_by_day:
            for tue_slot in slots_by_day[TUE][:3]:
                thu_slot = _find_matching_slot(slots_by_day[THU], tue_slot)
                if thu_slot is None:
                    continue

                tue_day = day_label_to_day.get(TUE)
                thu_day = day_label_to_day.get(THU)
                if not tue_day or not thu_day:
                    continue

                start_min = tue_slot.get("start_min")
                end_min = tue_slot.get("end_min")
                duration_min = end_min - start_min

                options.append({
                    "days": [TUE, THU],
                    "day_ids": [tue_day.id, thu_day.id],
                    "day_id": tue_day.id,
                    "start_min": start_min,
                    "end_min": end_min,
                    "duration_min": duration_min,
                    "block_indices": {tue_slot.get("index", 0), thu_slot.get("index", 0)},
                    "blocks_by_day": {tue_day.id: {tue_slot.get("index", 0)}, thu_day.id: {thu_slot.get("index", 0)}},
                    "slot_indexes": [tue_slot.get("index", 0), thu_slot.get("index", 0)],
                    "blocks_spanned": set(),
                    "slot_labels": [tue_slot.get("label", ""), thu_slot.get("label", "")],
                    "num_slots": 2,
                })

        if FRI in slots_by_day:
            day = day_label_to_day.get(FRI)
            if day:
                for slot in slots_by_day[FRI][:2]:
                    start_min = slot.get("start_min")
                    end_min = slot.get("end_min")
                    duration_min = end_min - start_min

                    options.append({
                        "days": [FRI],
                        "day_ids": [day.id],
                        "day_id": day.id,
                        "start_min": start_min,
                        "end_min": end_min,
                        "duration_min": duration_min,
                        "block_indices": {slot.get("index", 0)},
                        "blocks_by_day": {day.id: {slot.get("index", 0)}},
                        "slot_indexes": [slot.get("index", 0)],
                        "blocks_spanned": set(),
                        "slot_labels": [slot.get("label", "")],
                        "num_slots": 1,
                    })
    
    logger.warning(f"[FALLBACK] Generated {len(options)} time windows for subject {subj_id}")
    return options


def run_cp_scheduler(
    db: Session,
    course_id: int,
    year: Optional[int],
    semester: int,
    subject_ids: Optional[List[int]] = None,
    max_time_seconds: float = 300.0,
    college_id: Optional[int] = None,
    cluster_id_filter: Optional[int] = None,
    years: Optional[List[int]] = None,
    focus_subject_ids: Optional[List[int]] = None,
    block_capacity_overrides: Optional[Dict[Tuple[int, int, Any], int]] = None,
    block_count: int = 1,
    progress_callback: Optional[Any] = None,
) -> List[Dict]:
    # Debug: Log input parameters
    logger.info("\n" + "="*80)
    logger.info(f"Starting CP Scheduler with parameters:")
    logger.info(f"- course_id: {course_id}")
    logger.info(f"- year: {year}")
    logger.info(f"- semester: {semester}")
    logger.info(f"- subject_ids: {subject_ids}")
    logger.info(f"- college_id: {college_id}")
    logger.info(f"- cluster_id_filter: {cluster_id_filter}")
    logger.info(f"- focus_subject_ids: {focus_subject_ids}")
    logger.info(f"- block_count: {block_count}")
    logger.info("="*80 + "\n")
    """
    Generate schedule using OR-Tools Constraint Programming with cluster-based processing
    
    Args:
        db: Database session
        course_id: Course ID
        year: Legacy default year used when subjects are missing metadata
        semester: Semester (1-2)
        subject_ids: Optional list of subject IDs to schedule
        max_time_seconds: Maximum solver time in seconds
        college_id: Optional college scope for clustering
        cluster_id_filter: Optional filter to process a single cluster
        years: Optional list of requested year levels to include
        focus_subject_ids: Optional list of subject IDs to schedule
        block_capacity_overrides: Optional mapping {(course_id, year_level, block_id): capacity}
    
    Returns:
        List of schedule items (dicts with subject_id, instructor_id, room_id, day_id, time)
    """
    EARLY_THRESHOLD_MIN = 510  # 8:30 AM in minutes
    EARLY_PENALTY_WEIGHT = 5  # stronger penalty for very early slots
    normalized_years = sorted({int(y) for y in years if y is not None}) if years else []
    default_year = year if year is not None else (normalized_years[0] if normalized_years else None)
    focus_subject_ids_set = set(focus_subject_ids) if focus_subject_ids else None
    block_capacity_overrides = block_capacity_overrides or {}
    
    # Helper function for progress reporting
    def report_progress(message: str) -> None:
        if progress_callback is not None:
            try:
                progress_callback(message)
            except Exception:
                pass  # Ignore callback errors
    
    report_progress("📊 Loading subjects and instructors...")
    
    # Load data from database using stored procedures for optimization
    college_course_ids = []
    if college_id is not None:
        college_courses = db_procedures.get_courses_by_college(db=db, college_id=college_id)
        college_course_ids = [c.id for c in college_courses]
        logger.info(f"Found {len(college_course_ids)} courses in college {college_id}")
    
    # Debug: Log time bands and constraints
    logger.info("\nTime Band Constraints:")
    for band in TIME_BANDS:
        logger.info(f"- {band['label']}: {band['min_count']}-{band['max_count']} slots, "
                  f"Time: {band['min']//60:02d}:{band['min']%60:02d} to {band['max']//60:02d}:{band['max']%60:02d}")
    
    # If a cluster filter is provided with a college scope, schedule all subjects in that cluster across the college.
    # If no cluster filter but a college_id is provided, schedule all subjects across the college (optionally filtered by subject_ids).
    # Otherwise, default to scheduling by course_id (legacy behavior).
    # Use stored procedure for optimized subject loading
    if cluster_id_filter is not None and college_id is not None:
        subjects = db_procedures.get_subjects_for_scheduling(
            db=db,
            college_id=college_id,
            cluster_id=cluster_id_filter,
            subject_ids=subject_ids
        )
        logger.info(f"Loaded {len(subjects)} subjects for college {college_id} cluster {cluster_id_filter}.")
    elif college_id is not None:
        subjects = db_procedures.get_subjects_for_scheduling(
            db=db,
            college_id=college_id,
            course_id=course_id,
            subject_ids=subject_ids
        )
        logger.info(f"Loaded {len(subjects)} subjects for college {college_id} (no cluster filter).")
    else:
        # Note: Subjects are filtered by course_id for scheduling, but cluster assignments
        # come from college-wide clustering (all subjects in the college are clustered together)
        subjects = db_procedures.get_subjects_for_scheduling(
            db=db,
            course_id=course_id,
            subject_ids=subject_ids
        )

    if focus_subject_ids_set:
        filtered_subjects = [subject for subject in subjects if subject.id in focus_subject_ids_set]
        if len(filtered_subjects) != len(subjects):
            logger.info(
                "Filtered subjects by focus list: %d -> %d",
                len(subjects),
                len(filtered_subjects),
            )
        subjects = filtered_subjects
    
    # Debug: Log subjects to be scheduled with safe attribute access
    logger.info("\nSubjects to be scheduled:")
    for i, subject in enumerate(subjects[:10], 1):  # Show first 10 subjects
        try:
            # Safely get attributes with defaults
            code = getattr(subject, 'code', '?')
            name = getattr(subject, 'name', 'Unnamed')
            subj_id = getattr(subject, 'id', '?')
            subj_type = getattr(subject, 'subject_type', '?')
            hours_lec = getattr(subject, 'hours_lec', 0) or 0
            hours_lab = getattr(subject, 'hours_lab', 0) or 0
            year_level = getattr(subject, 'year_level', '?')
            
            logger.info(f"{i}. {code} - {name} (ID: {subj_id}, Type: {subj_type}, "
                      f"Hours: {hours_lec + hours_lab}, Year: {year_level})")
        except Exception as e:
            logger.warning(f"Error logging subject at index {i}: {str(e)}")
            logger.debug(f"Subject attributes: {dir(subject)}")
            
    if len(subjects) > 10:
        logger.info(f"... and {len(subjects) - 10} more subjects")
    
    # Note: Subjects from stored procedures are already up-to-date
    # If we need to refresh cluster assignments, query directly from database
    # Refresh only if subjects came from direct query (not stored procedure)
    # For stored procedure results, the data is already current
    subject_ids = [s.id for s in subjects]
    if subject_ids:
        # Re-query subjects from database to ensure we have latest cluster assignments
        # This ensures subjects are attached to the session and can be refreshed
        subjects_from_db = db.query(models.Subject).filter(models.Subject.id.in_(subject_ids)).all()
        # Create a lookup map
        subject_map = {s.id: s for s in subjects_from_db}
        # Replace stored procedure results with database objects (preserving order)
        subjects = [subject_map.get(s.id, s) for s in subjects if s.id in subject_map]
    
    if not subjects:
        logger.warning("No subjects to schedule")
        return []
    
    # =========================================================================
    # NSTP SPECIAL HANDLING
    # =========================================================================
    # NSTP subjects (NSTP1, NSTP 2, NSTP 12, etc.) get special treatment:
    # - Fixed day: Saturday (SAT)
    # - Fixed room: FIELD
    # - Fixed time: 8:00 AM - 11:00 AM
    # - Only instructor selection uses CP to avoid overlaps
    # 
    # We extract NSTP subjects and schedule them separately before the main CP solver
    # =========================================================================
    
    nstp_subjects = [s for s in subjects if _is_nstp_subject(s)]
    non_nstp_subjects = [s for s in subjects if not _is_nstp_subject(s)]
    nstp_scheduled_items = []
    
    if nstp_subjects:
        logger.info(f"\n{'='*60}")
        logger.info(f"NSTP PRE-SCHEDULING: Found {len(nstp_subjects)} NSTP subjects")
        logger.info(f"{'='*60}")
        
        # Get Saturday day_id
        sat_day = db.query(models.Day).filter(models.Day.label == NSTP_DAY_LABEL).first()
        if not sat_day:
            logger.warning(f"Saturday (SAT) not found in days table. NSTP subjects will be scheduled via normal CP.")
            # Keep NSTP subjects in the main scheduling pool
            non_nstp_subjects.extend(nstp_subjects)
            nstp_subjects = []
        else:
            # Get FIELD room
            field_room = db.query(models.Room).filter(models.Room.name == NSTP_ROOM_NAME).first()
            if not field_room:
                logger.warning(f"FIELD room not found in rooms table. NSTP subjects will be scheduled via normal CP.")
                non_nstp_subjects.extend(nstp_subjects)
                nstp_subjects = []
            else:
                # Get eligible instructors for NSTP subjects
                # We'll use CP only for instructor selection to avoid overlaps
                for nstp_subj in nstp_subjects:
                    nstp_code = getattr(nstp_subj, 'code', 'NSTP')
                    nstp_id = getattr(nstp_subj, 'id', 0)
                    
                    # Get instructors that can teach this specific NSTP subject
                    # NSTP 1 should match instructors with "NSTP1" or "NSTP 1"
                    # NSTP 2 should match instructors with "NSTP2" or "NSTP 2"
                    all_instructors = db.query(models.Instructor).all()
                    eligible_instrs = []
                    
                    # Determine which NSTP level this is
                    nstp_code_upper = nstp_code.upper().replace(" ", "")
                    is_nstp1 = "NSTP1" in nstp_code_upper or nstp_code_upper == "NSTP"
                    is_nstp2 = "NSTP2" in nstp_code_upper
                    
                    for instr in all_instructors:
                        assignable = (getattr(instr, 'assignable_courses', '') or '').upper().replace(" ", "")
                        # Check for specific NSTP level match
                        if is_nstp1 and ("NSTP1" in assignable or "NSTP 1" in (getattr(instr, 'assignable_courses', '') or '').upper()):
                            eligible_instrs.append(instr)
                        elif is_nstp2 and ("NSTP2" in assignable or "NSTP 2" in (getattr(instr, 'assignable_courses', '') or '').upper()):
                            eligible_instrs.append(instr)
                    
                    if not eligible_instrs:
                        # Fallback: try general NSTP instructors if no specific match found
                        for instr in all_instructors:
                            assignable = (getattr(instr, 'assignable_courses', '') or '').upper()
                            if 'NSTP' in assignable:
                                eligible_instrs.append(instr)
                    
                    if not eligible_instrs:
                        logger.warning(f"No instructors found for {nstp_code}. Using first 5 instructors as fallback.")
                        eligible_instrs = all_instructors[:5]
                    
                    # Find an instructor that doesn't have Saturday 8-11am conflict
                    selected_instructor = None
                    for instr in eligible_instrs:
                        # Check if instructor is already booked on Saturday 8-11am
                        existing = db.query(models.Schedule).filter(
                            models.Schedule.instructor_id == instr.id,
                            models.Schedule.day_id == sat_day.id,
                            models.Schedule.semester == semester,
                        ).first()
                        if not existing:
                            selected_instructor = instr
                            break
                    
                    if selected_instructor:
                        subj_course_id = getattr(nstp_subj, 'course_id', course_id) or course_id
                        subj_year = getattr(nstp_subj, 'year_level', year) or year or 1
                        
                        # Create NSTP entries for ALL blocks (block_count)
                        # Each block gets its own entry but same room/day/time
                        # This works because the unique constraint now includes block
                        try:
                            num_blocks = int(block_count) if block_count else 1
                        except (TypeError, ValueError):
                            num_blocks = 1
                        
                        for block_idx in range(1, num_blocks + 1):
                            block_label = _block_index_to_label(block_idx) or "A"
                            nstp_item = {
                                "subject_id": nstp_id,
                                "clone_subject_id": nstp_id,
                                "course_id": subj_course_id,
                                "instructor_id": selected_instructor.id,
                                "room_id": field_room.id,
                                "day_id": sat_day.id,  # sat_day is actually Sunday (variable name kept for compatibility)
                                "time": NSTP_TIME_LABEL,
                                "year": subj_year,
                                "semester": semester,
                                "block": block_label,  # Individual block label (A, B, C, etc.)
                                "start_min": NSTP_START_MIN,
                                "end_min": NSTP_END_MIN,
                            }
                            nstp_scheduled_items.append(nstp_item)
                            logger.info(f"  ✓ NSTP scheduled: {nstp_code} block {block_label} -> Sunday 8-11am, FIELD, Instructor {selected_instructor.id}")
                    else:
                        logger.warning(f"  ✗ NSTP {nstp_code}: No available instructor for Sunday 8-11am")
                        # Fall back to normal scheduling
                        non_nstp_subjects.append(nstp_subj)
        
        logger.info(f"NSTP pre-scheduling complete: {len(nstp_scheduled_items)} scheduled, {len([s for s in nstp_subjects if s not in non_nstp_subjects])} subjects handled")
    
    # Use non-NSTP subjects for the main CP solver
    subjects = non_nstp_subjects

    # Expand subjects per student block (block_count) using lightweight in-memory clones.
    try:
        block_count_int = int(block_count)
    except (TypeError, ValueError):
        block_count_int = 1
    if block_count_int < 1:
        block_count_int = 1
    block_count = block_count_int

    if block_count == 1:
        # Tag original subjects for single-block scheduling.
        for subj in subjects:
            try:
                setattr(subj, "original_subject_id", getattr(subj, "id", None))
            except Exception:
                pass
            try:
                setattr(subj, "student_block", 1)
            except Exception:
                pass
    else:
        # Create synthetic per-block clones so each (subject, block) can be scheduled independently.
        try:
            max_subject_id = max(
                int(getattr(s, "id"))
                for s in subjects
                if getattr(s, "id", None) is not None
            )
        except Exception:
            max_subject_id = 0

        id_stride = max_subject_id + 1 if max_subject_id is not None else 1000000
        expanded_subjects = []
        for subj in subjects:
            subj_id_val = getattr(subj, "id", None)
            try:
                subj_id_int = int(subj_id_val)
            except Exception:
                continue

            for student_block_index in range(1, block_count + 1):
                new_id = subj_id_int + student_block_index * id_stride
                clone = _SubjectBlockClone()
                for attr_name, attr_value in subj.__dict__.items():
                    if attr_name.startswith("_"):
                        continue
                    setattr(clone, attr_name, attr_value)
                setattr(clone, "id", new_id)
                setattr(clone, "original_subject_id", subj_id_int)
                setattr(clone, "student_block", student_block_index)
                expanded_subjects.append(clone)

        subjects = expanded_subjects
    
    # Load time blocks from database (time windows that subjects can be scheduled into)
    # These define the real registrar time grid (various durations, not just 30 minutes).
    time_blocks = []
    time_blocks_by_day = defaultdict(list)
    try:
        db_time_blocks = db.query(models.TimeBlock).order_by(models.TimeBlock.block_id).all()
        if db_time_blocks:
            for tb in db_time_blocks:
                day_key = int(tb.day_id)
                tb_data = {
                    "block_id": tb.block_id,
                    "day_id": day_key,
                    "label": tb.label,
                    "start": tb.start_time,
                    "end": tb.end_time,
                    # Recompute minutes from start_time/end_time to avoid relying on
                    # any stored offsets in the DB columns.
                    "start_min": time_to_minutes(tb.start_time),
                    "end_min": time_to_minutes(tb.end_time),
                    "is_lab": tb.is_lab,
                }
                time_blocks.append(tb_data)
                time_blocks_by_day[day_key].append(tb_data)
            logger.info("Loaded %d time blocks from database", len(time_blocks))
        else:
            logger.warning("No time blocks found in database")
    except Exception as e:
        logger.warning("Error loading time blocks from database: %s", e)

    time_block_ids = [tb["block_id"] for tb in time_blocks]
    time_block_by_id = {tb["block_id"]: tb for tb in time_blocks}
    max_block_id = max(time_block_ids) if time_block_ids else 0
    
    logger.info("Using %d time blocks for scheduling", len(time_blocks))
    
    # Log cluster information for debugging
    cluster_distribution = {}
    for subject in subjects:
        cluster_id = subject.cluster if subject.cluster is not None else -1
        cluster_distribution[cluster_id] = cluster_distribution.get(cluster_id, 0) + 1
    cluster_details = ", ".join(
        f"{cid}:{count}" for cid, count in sorted(cluster_distribution.items())
    )
    logger.info(
        "Cluster distribution summary (total_subjects=%d): %s",
        len(subjects),
        cluster_details or "none",
    )
    years_label = normalized_years or ([default_year] if default_year is not None else "all")
    if college_id is not None:
        if cluster_id_filter is not None:
            logger.info(f"Cluster distribution (college {college_id}, cluster={cluster_id_filter}): {cluster_distribution}")
        else:
            logger.info(f"Loaded {len(subjects)} subjects for college {college_id}. Cluster distribution: {cluster_distribution}")
    else:
        logger.info(
            "Loaded %d subjects for course %s (years=%s). Cluster distribution: %s",
            len(subjects),
            course_id,
            years_label,
            cluster_distribution,
        )
    # Load all instructors (no is_active filter as it doesn't exist in the model)
    instructors = db.query(models.Instructor).all()
    logger.info(f"Loaded {len(instructors)} instructors")

    deductions = {
        "program chair": 3,
        "college secretary": 3,
        "dean": 12,
        "associate dean": 12,
        "director": 12,
    }

    instructor_limit_minutes: Dict[int, int] = {}
    for inst in instructors:
        try:
            inst_id = int(getattr(inst, "id"))
        except Exception:
            continue
        employment_type = (getattr(inst, "employment_type", None) or "regular").strip().lower()
        designation = (getattr(inst, "designation", None) or "").strip().lower()
        if employment_type == "visiting":
            limit_hours = 30
        else:
            deduction = deductions.get(designation, 0) if designation else 0
            limit_hours = max(0, 24 - deduction)
        instructor_limit_minutes[inst_id] = int(limit_hours) * 60

    instructor_current_minutes: Dict[int, int] = defaultdict(int)
    try:
        all_timeslots = db.query(models.Timeslot).all()
    except Exception:
        all_timeslots = []
    timeslot_minutes_map = {}
    for ts in all_timeslots:
        try:
            timeslot_minutes_map[(str(getattr(ts, "label", "") or ""), int(getattr(ts, "day")))] = (
                int(getattr(ts, "start_min")),
                int(getattr(ts, "end_min")),
            )
        except Exception:
            continue

    try:
        existing_scheds = (
            db.query(models.Schedule)
            .filter(models.Schedule.semester == semester, models.Schedule.instructor_id.isnot(None))
            .all()
        )
    except Exception:
        existing_scheds = []

    for sched in existing_scheds:
        instr_id = getattr(sched, "instructor_id", None)
        if instr_id is None:
            continue
        try:
            instr_id_int = int(instr_id)
        except Exception:
            continue
        raw_time = (getattr(sched, "time", None) or "").strip()
        if not raw_time:
            continue
        time_label = re.sub(r"^(M|T|W|TH|F)\s+", "", raw_time, flags=re.IGNORECASE)
        parsed = _parse_time_range_minutes(time_label)
        if parsed:
            start_min, end_min = parsed
            instructor_current_minutes[instr_id_int] += max(0, int(end_min) - int(start_min))
            continue
        day_id_val = getattr(sched, "day_id", None)
        if day_id_val is None:
            continue
        try:
            day_id_int = int(day_id_val)
        except Exception:
            continue
        ts_key = (time_label, day_id_int)
        rng = timeslot_minutes_map.get(ts_key)
        if rng:
            start_min, end_min = rng
            instructor_current_minutes[instr_id_int] += max(0, int(end_min) - int(start_min))
    
    # Load all rooms ordered by capacity
    rooms = db.query(models.Room).order_by(models.Room.capacity).all()
    logger.info(f"Loaded {len(rooms)} rooms")
    
    # Debug: Log resource counts
    logger.info("\nResource Availability:")
    logger.info(f"- Total active rooms: {len(rooms)}")
    if rooms:
        logger.info(f"  - Capacity range: {min(r.capacity for r in rooms)} to {max(r.capacity for r in rooms)}")
    logger.info(f"- Total active instructors: {len(instructors)}")
    
    # Load days from database
    days = db.query(models.Day).order_by(models.Day.id).all()
    day_labels = [d.label for d in days]
    day_id_map = {d.label: d.id for d in days}
    day_id_to_label = {d.id: d.label for d in days}
    
    # Build slots_by_day directly from DB time blocks (real registrar grid)
    slots_by_day = {day: [] for day in day_labels}
    for day in days:
        day_blocks = time_blocks_by_day.get(day.id, [])
        # Sort by start_min to ensure correct temporal order
        day_blocks_sorted = sorted(day_blocks, key=lambda tb: tb["start_min"])
        for local_idx, tb in enumerate(day_blocks_sorted):
            day_label = day.label
            slots_by_day[day_label].append({
                "day": day_label,
                "index": local_idx,  # index is per-day; uniqueness is (day_id, index)
                "label": tb["label"],
                "start": tb["start"],
                "end": tb["end"],
                "start_min": tb["start_min"],
                "end_min": tb["end_min"],
                "is_lab": tb["is_lab"],  # informational only; not a hard restriction
            })

    # Create mapping from (day_id, start_min) to block index (per-day index)
    slot_to_block_map = {}
    for day in days:
        day_slots = slots_by_day.get(day.label, [])
        for slot in day_slots:
            key = (day.id, slot["start_min"])
            slot_to_block_map[key] = slot["index"]
    
    logger.info(f"Generated {sum(len(slots) for slots in slots_by_day.values())} total time slots")
    
    # Debug: Check for subjects with no valid start options
    logger.info("\nChecking subject scheduling feasibility:")
    for subject in subjects:
        options = generate_subject_start_options(
            subject=subject,
            slots_by_day=slots_by_day,
            slot_to_block_map=slot_to_block_map,
            days=days,
            logger=logger
        )
        if not options:
            logger.warning(f"⚠️ No valid start options for subject: {subject.code} - {subject.name} "
                         f"(ID: {subject.id}, Type: {subject.subject_type}, "
                         f"Hours: {subject.hours_lec+subject.hours_lab})")
            
            # Additional debug for problematic subjects
            logger.debug(f"Subject details: {subject.__dict__}")
            logger.debug(f"Required hours: LEC={subject.hours_lec}, LAB={subject.hours_lab}")

    if not instructors or not rooms or not days:
        logger.warning("Missing required data: instructors=%d, rooms=%d, days=%d", 
                      len(instructors), len(rooms), len(days))
        return []
    
    # Get existing bookings (to avoid conflicts with other courses)
    # For college-wide scheduling of a cluster, do not exclude any course
    exclude_id = None if college_id is not None else course_id
    context_years = years if years else ([year] if year is not None else None)
    
    # Build eligibility maps for instructors and rooms
    logger.info("\nBuilding eligibility maps...")
    course_to_instructors, course_to_rooms = build_eligibility_maps(subjects, instructors, rooms, db)
    # Create room_id_to_name and room_by_id mappings
    room_id_to_name = {room.id: room.name for room in rooms}
    room_by_id = {room.id: room for room in rooms}
    
    # Debug: Log detailed eligibility information
    logger.info("\nDetailed Eligibility Debug:")
    
    # Log subjects being scheduled
    logger.info("\nSubjects to be scheduled:")
    for subj in subjects:
        logger.info(f"- Subject ID: {subj.id}, Code: {getattr(subj, 'code', 'N/A')}, "
                   f"Type: {getattr(subj, 'type', 'N/A')}, "
                   f"Course: {getattr(subj, 'course_id', 'N/A')}, "
                   f"Year: {getattr(subj, 'year_level', 'N/A')}")
    
    # Log instructors and their colleges
    logger.info("\nAvailable Instructors:")
    for inst in instructors:
        logger.info(f"- Instructor ID: {inst.id}, Name: {getattr(inst, 'name', 'N/A')}, "
                  f"College: {getattr(inst, 'college_id', 'N/A')}, "
                  f"Assignable: {getattr(inst, 'assignable_courses', 'N/A')}")
    
    # Log rooms and their types
    logger.info("\nAvailable Rooms:")
    for room in rooms:
        logger.info(f"- Room ID: {room.id}, Name: {getattr(room, 'name', 'N/A')}, "
                  f"Type: {getattr(room, 'type', 'N/A')}, "
                  f"Capacity: {getattr(room, 'capacity', 'N/A')}")
    
    # Log eligibility issues with more details
    logger.info("\n" + "="*80)
    logger.info("ELIGIBILITY ANALYSIS")
    logger.info("="*80)
    
    for subject in subjects:
        course_key = (subject.course_id, subject.year_level or default_year)
        subj_code = (getattr(subject, 'code', '') or '').upper().strip()
        subj_type = getattr(subject, 'type', 'N/A')
        subj_college = getattr(subject, 'college_id', None) or college_id
        subj_id = getattr(subject, "id", None)
        
        # Log subject header
        logger.info("\n" + "-"*60)
        logger.info(f"SUBJECT: {subj_code} (ID: {subject.id})")
        logger.info(f"Type: {subj_type}, College: {subj_college or 'Not specified'}")
        
        # Check instructor eligibility (maps are per-subject, keyed by subject.id)
        eligible_instr_list = course_to_instructors.get(subj_id, []) if subj_id is not None else []
        if not eligible_instr_list:
            logger.warning("\n⚠️ NO ELIGIBLE INSTRUCTORS FOUND")
            
            if not instructors:
                logger.warning("  - No instructors available in the system")
                continue
                
            # Detailed instructor analysis
            logger.info("\nInstructor Analysis:")
            logger.info("-"*30)
            
            # Check college matches
            if subj_college:
                college_matches = [i for i in instructors if getattr(i, 'college_id', None) == subj_college]
                logger.info(f"College Matches: {len(college_matches)}/{len(instructors)}")
                
                # Show sample of matching instructors
                if college_matches:
                    logger.info("  Sample matching instructors:")
                    for inst in college_matches[:3]:  # Show first 3 matches
                        logger.info(f"  - {getattr(inst, 'name', 'N/A')} (ID: {inst.id})")
            
            # Check subject code in assignable courses
            if subj_code:
                assignable_matches = [i for i in instructors 
                                    if subj_code in (getattr(i, 'assignable_courses', '') or '').upper()]
                logger.info(f"\nSubject Code in Assignable Courses: {len(assignable_matches)}/{len(instructors)}")
                
                if not assignable_matches:
                    logger.warning(f"  - No instructors have {subj_code} in their assignable courses")
                    
                    # Show what courses instructors are actually assigned to
                    unique_assignments = set()
                    for inst in instructors[:5]:  # Check first 5 instructors
                        courses = (getattr(inst, 'assignable_courses', '') or '').upper()
                        if courses:
                            unique_assignments.update(courses.split(','))
                    
                    if unique_assignments:
                        logger.info("\nSample of assignable courses found:")
                        logger.info("  " + ", ".join(list(unique_assignments)[:5]))
        
        # Check room eligibility (maps are per-subject, keyed by subject.id)
        eligible_room_list = course_to_rooms.get(subj_id, []) if subj_id is not None else []
        if not eligible_room_list:
            logger.warning("\n⚠️ NO ELIGIBLE ROOMS FOUND")
            
            if not rooms:
                logger.warning("  - No rooms available in the system")
                continue
                
            # Room type analysis
            logger.info("\nRoom Analysis:")
            logger.info("-"*30)
            
            # Count rooms by type
            room_types = {}
            for room in rooms:
                r_type = getattr(room, 'type', 'UNKNOWN')
                room_types[r_type] = room_types.get(r_type, 0) + 1
            
            logger.info("Available room types and counts:")
            for r_type, count in room_types.items():
                logger.info(f"  - {r_type}: {count} rooms")
            
            logger.info(f"\nSubject requires room type: {subj_type}")
            if subj_type and subj_type.upper() in [rt.upper() for rt in room_types.keys()]:
                logger.warning(f"  - Found matching room type but no rooms available. Check other constraints.")
            
            # Show sample rooms
            logger.info("\nSample of available rooms:")
            for room in rooms[:5]:  # Show first 5 rooms
                logger.info(f"  - {getattr(room, 'name', 'N/A')} (Type: {getattr(room, 'type', 'N/A')}, "
                          f"Capacity: {getattr(room, 'capacity', 'N/A')}")

    # Create time slots for each day
    day_labels = [d.label for d in days]
    day_id_map = {d.label: d.id for d in days}  # For time_label to block_index conversion
    all_slots = get_all_time_slots(day_labels)

    # Get existing bookings from database
    logger.info("\nLoading existing bookings...")
    booked_room_slots, booked_instr_slots = get_existing_bookings(
        db=db,
        years=normalized_years,
        semester=semester,
        exclude_course_id=course_id,
        slots_by_day=slots_by_day,
        day_id_map=day_id_map,
    )
    
    # Debug: Log booking counts (avoid duplicate messages when counts are zero)
    if booked_room_slots:
        logger.info(f"- Found {len(booked_room_slots)} existing room bookings")
    else:
        logger.info("- No existing room bookings found")

    if booked_instr_slots:
        logger.info(f"- Found {len(booked_instr_slots)} existing instructor bookings")
    else:
        logger.info("- No existing instructor bookings found")
    
    # Create mapping from time slot minutes to time block_id
    # Each time block is 30 minutes (1 slot of 30 minutes)
    slot_to_db_block_map = {}  # (day_id, start_min) -> block_id (optional DB mapping)
    unmapped_slots = []  # Track slots that couldn't be mapped
    # ... (rest of the code remains the same)
    block_id_collisions = []  # Track if same block_id appears for different days (shouldn't happen with day_id in key)
    
    for day in days:
        day_slots = slots_by_day.get(day.label, [])
        day_time_blocks = time_blocks_by_day.get(int(day.id), [])
        for slot in day_slots:
            slot_start_min = slot["start_min"]
            mapped = False
            # Find which time block this slot belongs to (day-specific)
            key = (day.id, slot_start_min)
            for tb in day_time_blocks:
                if tb["start_min"] <= slot_start_min < tb["end_min"]:
                    block_id = tb["block_id"]
                    # Verify block_id uniqueness per (day_id, start_min)
                    if key in slot_to_db_block_map:
                        existing_block_id = slot_to_db_block_map[key]
                        if existing_block_id != block_id:
                            block_id_collisions.append((day.label, slot_start_min, block_id, existing_block_id))
                    else:
                        slot_to_db_block_map[key] = block_id
                    mapped = True
                    break
            if not mapped:
                unmapped_slots.append((day.label, slot["label"], slot_start_min))
    
    # DEBUG: Report mapping coverage (DB time_blocks vs logical slots)
    total_slots = sum(len(slots_by_day.get(day.label, [])) for day in days)
    mapped_count = len(slot_to_db_block_map)
    if unmapped_slots:
        logger.warning(
            "DB time_blocks cover only %d/%d logical time slots; some slots have no matching DB block. "
            "First 10 unmapped: %s",
            mapped_count, total_slots, unmapped_slots[:10]
        )
    else:
        logger.info(
            "✓ DB time_blocks mapping: %d/%d slots mapped successfully (100%%)",
            mapped_count, total_slots
        )
    
    if block_id_collisions:
        logger.warning(
            "Detected %d block_id collisions in DB time_blocks mapping (same (day_id, start_min) -> different block_ids): %s",
            len(block_id_collisions), block_id_collisions[:5]
        )
    
    # DEBUG: Verify block_id distribution across days (DB mapping only)
    block_ids_by_day = defaultdict(set)
    for (day_id, start_min), block_id in slot_to_db_block_map.items():
        day_label = next((d.label for d in days if d.id == day_id), "?")
        block_ids_by_day[day_label].add(block_id)
    
    logger.debug(
        "DB block ID distribution: %s",
        {label: (len(block_ids), f"IDs: {sorted(list(block_ids))[:5]}...") 
         for label, block_ids in block_ids_by_day.items()}
    )
    
    # Create slot indices for reference
    slot_indices = list(range(len(all_slots)))
    
    # Map room IDs to names
    room_id_to_name = {r.id: r.name for r in rooms}
    
    # Precompute room cluster mapping - check if rooms have valid cluster assignments
    # A room has a valid cluster if cluster is not None and not -1
    rooms_cluster_present = any(
        r.cluster is not None and r.cluster != -1 and r.cluster >= 0 
        for r in rooms
    )
    if rooms_cluster_present:
        room_cluster_map = {
            r.id: (r.cluster if (r.cluster is not None and r.cluster != -1) else -1) 
            for r in rooms
        }
        logger.info(f"Using room cluster assignments: {sum(1 for c in room_cluster_map.values() if c != -1)}/{len(rooms)} rooms have clusters")
    else:
        # Deterministic fallback: assign rooms to clusters based on sorted room ID modulo
        unique_clusters = sorted([s.cluster for s in subjects if s.cluster is not None and s.cluster != -1])
        num_clusters = len(unique_clusters) if unique_clusters else 1
        log_once("Rooms have no valid cluster assignments -> using deterministic room-to-cluster mapping")
        # Sort rooms by ID for deterministic assignment
        sorted_rooms = sorted(rooms, key=lambda r: r.id)
        room_cluster_map = {r.id: (idx % num_clusters) for idx, r in enumerate(sorted_rooms)}
        logger.info(f"Deterministically assigned {len(rooms)} rooms to {num_clusters} clusters")
    
    # Group subjects by cluster
    subjects_by_cluster = defaultdict(list)
    for subject in subjects:
        cluster_id = subject.cluster if subject.cluster is not None else -1
        subjects_by_cluster[cluster_id].append(subject)
    
    # Sort clusters; if a specific cluster is requested, keep only that one
    cluster_items = sorted(subjects_by_cluster.items(), key=lambda x: x[0])
    if cluster_id_filter is not None:
        cluster_items = [(cid, subjs) for (cid, subjs) in cluster_items if cid == cluster_id_filter]
    
    # Global booking maps (inter-cluster propagation) - using block_index
    booked_room_slots_global = set(booked_room_slots)  # (room_name, day_id, block_index)
    booked_instr_slots_global = set(booked_instr_slots)  # (instr_id, day_id, block_index)

    # Additional global booking maps using real minute ranges.
    # This is necessary because TIME_BLOCKS contains overlapping windows (e.g., 7:00–8:30 and 7:30–8:30),
    # so a conflict cannot be represented reliably by (day_id, block_index) alone.
    booked_room_ranges_global = defaultdict(list)  # (room_name, day_id) -> [(start_min, end_min), ...]
    booked_instr_ranges_global = defaultdict(list)  # (instr_id, day_id) -> [(start_min, end_min), ...]

    # Seed range-based bookings from existing bookings (DB + other courses).
    # We map (day_id, block_index) -> (start_min, end_min) from the logical slot grid.
    slot_range_by_day_and_index = {}
    for d in days:
        for s in slots_by_day.get(d.label, []):
            try:
                slot_range_by_day_and_index[(int(d.id), int(s["index"]))] = (int(s["start_min"]), int(s["end_min"]))
            except Exception:
                continue

    for room_name, day_id, block_index in booked_room_slots_global:
        try:
            day_id_i = int(day_id)
            block_i = int(block_index)
        except Exception:
            continue
        rng = slot_range_by_day_and_index.get((day_id_i, block_i))
        if rng is not None:
            booked_room_ranges_global[(room_name, day_id_i)].append(rng)

    for instr_id, day_id, block_index in booked_instr_slots_global:
        try:
            day_id_i = int(day_id)
            block_i = int(block_index)
            instr_id_i = int(instr_id)
        except Exception:
            continue
        rng = slot_range_by_day_and_index.get((day_id_i, block_i))
        if rng is not None:
            booked_instr_ranges_global[(instr_id_i, day_id_i)].append(rng)
    
    all_scheduled_items = []
    subject_lookup = {s.id: s for s in subjects}

    # Global set of codes that have at least one LAB subject anywhere.
    # Used for soft preferences: only LECs with NO LAB counterpart should
    # strongly prefer Friday; LECs with LABs are governed by LEC/LAB pairing.
    codes_with_labs_global: Set[str] = set()
    for subj in subjects:
        try:
            subj_type = (getattr(subj, "type", "") or "").upper().strip()
            if subj_type != "LAB":
                continue
            code_val = (getattr(subj, "code", "") or "").upper().strip()
            if code_val:
                codes_with_labs_global.add(code_val)
        except Exception:
            continue

    # CRITICAL: Track scheduled results from previous clusters for cross-cluster constraints
    # Format: (year_level, student_block_index, day_id) -> [(start_min, end_min), ...] from already-scheduled subjects
    cross_cluster_scheduled_ranges = defaultdict(list)  # (year_level, student_block_index, day_id) -> [(start_min, end_min), ...]

    # NEW: Global map to enforce LEC/LAB instructor consistency across clusters.
    # Key: (subject_code_upper, course_id, year_level, student_block_index) -> instructor_id
    global_lec_instr_by_key: Dict[Tuple[str, int, int, int], int] = {}

    day_distribution_tracker = defaultdict(set)  # day_id -> set(subject_id)

    # Main cluster loop
    current_student_block_index = None
    block_cluster_plan = []
    if block_count >= 2:
        for student_block_index in range(1, block_count + 1):
            for cid, subjs in cluster_items:
                filtered = []
                for s in subjs:
                    try:
                        sb = int(getattr(s, "student_block", 1) or 1)
                    except Exception:
                        sb = 1
                    if sb == student_block_index:
                        filtered.append(s)
                if filtered:
                    block_cluster_plan.append((student_block_index, cid, filtered))
    else:
        for cid, subjs in cluster_items:
            if subjs:
                block_cluster_plan.append((1, cid, subjs))

    for student_block_index, cluster_id, cluster_subjects in block_cluster_plan:
        if current_student_block_index != student_block_index:
            current_student_block_index = student_block_index
            cross_cluster_scheduled_ranges = defaultdict(list)
            day_distribution_tracker = defaultdict(set)

        logger.info("=== Solving cluster %s (%d subjects) ===", cluster_id, len(cluster_subjects))
        
        # Log subject IDs in this cluster for debugging
        subject_ids_in_cluster = [s.id for s in cluster_subjects]
        logger.info("Cluster %s subject IDs: %s", cluster_id, subject_ids_in_cluster)
        
        if cluster_id == -1 or len(cluster_subjects) == 0:
            logger.info("Skipping invalid/empty cluster.")
            # CRITICAL: Don't skip cluster -1, process it with fallback logic
            if cluster_id == -1 and len(cluster_subjects) > 0:
                logger.warning("Processing cluster -1 (unclustered subjects) with %d subjects", len(cluster_subjects))
            else:
                continue
        
        # Pre-greedy populate hints (but do not permanently modify global bookings - copy sets)
        saved_booked_rooms = set(booked_room_slots_global)
        saved_booked_instrs = set(booked_instr_slots_global)
        
        greedy_hints = greedy_initial_schedule(
            cluster_subjects,
            course_to_instructors,
            course_to_rooms,
            slots_by_day,
            saved_booked_rooms,
            saved_booked_instrs,
            rooms,
            days
        )
        
        # Restore booked sets - the actual booking will be applied after solver confirms chosen starts
        booked_room_slots_global = saved_booked_rooms
        booked_instr_slots_global = saved_booked_instrs
        
        model = cp_model.CpModel()
        
        subject_ids_list = [s.id for s in cluster_subjects]
        id_to_code = {s.id: s.code.upper().strip() for s in cluster_subjects}
        instructor_ids = [i.id for i in instructors]
        room_ids = [r.id for r in rooms]
        
        start_vars = {}
        start_covers = {}
        start_options_count = defaultdict(int)
        
        # Build start options with pruning (capacity + current global bookings + instructor availability)
        subjects_without_options = []
        subjects_skipped_count = 0
        
        # PRECOMPUTE: Subject lookup dict (no linear search)
        subject_lookup_cluster = {s.id: s for s in cluster_subjects}

        # Ensure the global lookup includes any per-block clone subjects used in this cluster.
        # Otherwise, extraction may not be able to map clone_subject_id -> original_subject_id.
        try:
            subject_lookup.update(subject_lookup_cluster)
        except Exception:
            pass
        
        # PRECOMPUTE: Instructor availability per time slot for faster pruning
        # Using block_index for efficient numeric conflict checking
        instructor_availability = defaultdict(lambda: defaultdict(set))  # instructor_id -> day_id -> {available block_indices}
        # Track instructor bookings by block index ranges for efficient overlap checking
        instructor_booked_blocks = defaultdict(lambda: defaultdict(set))  # instructor_id -> day_id -> {block_index, ...}
        
        for instructor_id in instructor_ids:
            for day in days:
                day_slots = slots_by_day.get(day.label, [])
                for slot in day_slots:
                    block_index = slot["index"]
                    if (instructor_id, day.id, block_index) not in booked_instr_slots_global:
                        instructor_availability[instructor_id][day.id].add(block_index)
                    else:
                        # Track booked block indices for overlap checking
                        instructor_booked_blocks[instructor_id][day.id].add(block_index)
        
        # PRECOMPUTE: Room booked block indices for overlap checking
        # booked_room_slots_global already uses block_index, so direct conversion
        room_booked_blocks = defaultdict(lambda: defaultdict(set))  # room_name -> day_id -> {block_index, ...}
        for room_name, day_id, block_index in booked_room_slots_global:
            room_booked_blocks[room_name][day_id].add(block_index)
        
        # PRECOMPUTE: Instructor teaching assignments by year_level for student conflict detection
        instructor_year_assignments = defaultdict(set)  # instructor_id -> {year_level, ...}
        for subject in cluster_subjects:
            # CRITICAL: Maps are now keyed by subject.id, not course_id
            eligible_instrs = course_to_instructors.get(subject.id, [])
            year_level = subject.year_level or default_year
            for instr_id in eligible_instrs:
                instructor_year_assignments[instr_id].add(year_level)
        
        # PRECOMPUTE: Room availability per day (room -> day -> available block_indices)
        # CRITICAL FIX: Use room_id as key (not room_name) for consistency with lookup
        room_available_blocks = defaultdict(lambda: defaultdict(set))  # room_id -> day_id -> {available block_index, ...}
        for room in rooms:
            room_id = room.id
            room_name = room_id_to_name.get(room_id)
            if not room_name:
                continue
            for day in days:
                day_slots = slots_by_day.get(day.label, [])
                booked_blocks = room_booked_blocks.get(room_name, {}).get(day.id, set())
                all_block_indices = {slot["index"] for slot in day_slots}
                room_available_blocks[room_id][day.id] = all_block_indices - booked_blocks
        
        # PRECOMPUTE: Instructor availability per day (instructor -> day -> available block_indices)
        instructor_available_blocks = defaultdict(lambda: defaultdict(set))  # instructor_id -> day_id -> {available block_index, ...}
        for instructor_id in instructor_ids:
            for day in days:
                day_slots = slots_by_day.get(day.label, [])
                booked_blocks = instructor_booked_blocks.get(instructor_id, {}).get(day.id, set())
                all_block_indices = {slot["index"] for slot in day_slots}
                instructor_available_blocks[instructor_id][day.id] = all_block_indices - booked_blocks
        
        # NEW APPROACH: Generate all start options first using robust window generation
        # Determine adaptive sampling based on problem size
        num_total_subjects = len(cluster_subjects)
        avg_slots_per_day = sum(len(slots_by_day.get(d.label, [])) for d in days) // max(1, len(days))
        if avg_slots_per_day > 30 and num_total_subjects > 20:
            # Large problem: use sampling to reduce options
            sampling = 2
        elif avg_slots_per_day > 20:
            sampling = 1  # Medium: full enumeration
        else:
            sampling = 1  # Small: full enumeration
        
        all_start_options = generate_all_subject_start_options(
            subjects=cluster_subjects,
            days=days,
            slots_by_day=slots_by_day,
            slot_to_block_map=slot_to_block_map,
            sampling=sampling,
        )
        
        # NEW APPROACH: Create CP variables from options with room/instructor filtering
        start_presence_map = {}  # (subject_id, day_id, start_min, opt_idx) -> presence_var
        start_interval_map = {}  # (subject_id, day_id, start_min, opt_idx) -> interval_var
        start_metadata = {}  # (subject_id, day_id, start_min, opt_idx) -> metadata
        start_vars = {}  # Keep for backward compatibility: (subject_id, room_id, global_start, instructor_id, num_slots) -> var
        start_covers = {}  # Keep for backward compatibility
        presence_weekly_minutes = {}
        instructor_presence_terms = defaultdict(list)  # instructor_id -> [(presence_var, weekly_minutes), ...]
        
        # Global limit: maximum variables per subject to prevent memory explosion
        # OPTIMIZED: Reduced from 5000 to 300 for faster solving while maintaining schedulability
        MAX_VARIABLES_PER_SUBJECT = 1000
        
        # Track if this is cluster 0 and first subject for detailed debug logging
        is_cluster_0 = (cluster_id == 0)
        first_subject_in_cluster_0_logged = False
        
        for subject_id in subject_ids_list:
            subject = subject_lookup_cluster.get(subject_id)
            if not subject:
                continue
            
            code = id_to_code.get(subject_id, f"ID_{subject_id}")  # For logging/debugging
            
            # Always get a LIST - ensure type safety
            # CRITICAL: Maps are now keyed by subject.id, not course_id
            eligible_rooms = course_to_rooms.get(subject_id, [])
            if not isinstance(eligible_rooms, list):
                eligible_rooms = list(eligible_rooms) if eligible_rooms else []
            
            eligible_instrs = course_to_instructors.get(subject_id, [])
            if not isinstance(eligible_instrs, list):
                eligible_instrs = list(eligible_instrs) if eligible_instrs else []
            
            # DEBUG: Log actual lists to verify subject_id lookup is working
            logger.debug(
                "Subject %s (ID:%d) eligible rooms: %s",
                code, subject_id, eligible_rooms
            )
            logger.debug(
                "Subject %s (ID:%d) eligible instructors: %s",
                code, subject_id, eligible_instrs
            )
            
            # Prefer rooms within the same cluster; if none, keep original eligible rooms
            # NOTE: This may reduce eligible_rooms, but it's intentional cluster filtering
            original_eligible_rooms_count = len(eligible_rooms)
            if rooms_cluster_present:
                subj_cluster = subject.cluster if subject.cluster is not None else -1
                if subj_cluster != -1:
                    rooms_in_same_cluster = [
                        rid for rid in eligible_rooms
                        if room_cluster_map.get(rid, -1) == subj_cluster
                    ]
                    if rooms_in_same_cluster:
                        eligible_rooms = rooms_in_same_cluster
                        logger.debug(
                            "Subject %s: Cluster filtering reduced rooms from %d to %d (cluster %d)",
                            code, original_eligible_rooms_count, len(eligible_rooms), subj_cluster
                        )
            
            # Detailed debug logging for FIRST subject in cluster 0
            should_log_detailed = (is_cluster_0 and not first_subject_in_cluster_0_logged)
            
            if should_log_detailed:
                logger.debug("DEBUG - Eligible rooms BEFORE filtering: %d", len(eligible_rooms))
                logger.debug("DEBUG - Eligible instructors BEFORE filtering: %d", len(eligible_instrs))
            else:
                # Regular logging for other subjects
                logger.debug(
                    "Subject %d (%s): Eligible rooms BEFORE filtering: %d, Eligible instructors BEFORE filtering: %d",
                    subject_id, code, len(eligible_rooms), len(eligible_instrs)
                )
            
            # CRITICAL: Use len() == 0 check, NOT truthy check
            # FALLBACK: If no eligible rooms/instructors, add fallback options to ensure scheduling
            if len(eligible_rooms) == 0 or len(eligible_instrs) == 0:
                reason = "no eligible instructors" if len(eligible_instrs) == 0 else "no eligible rooms"
                logger.warning(f"Subject {code} ({subject_id}) has {reason} - adding fallback eligibility")
                logger.warning(f"  - Original eligible rooms: {eligible_rooms}")
                logger.warning(f"  - Original eligible instructors: {eligible_instrs}")
                
                # FALLBACK: Add all rooms as eligible if none specified
                if len(eligible_rooms) == 0:
                    eligible_rooms = [room.id for room in rooms]
                    logger.warning(f"  - Fallback: using all {len(eligible_rooms)} rooms")
                
                # FALLBACK: Add all instructors as eligible if none specified  
                if len(eligible_instrs) == 0:
                    eligible_instrs = [inst.id for inst in instructors]
                    logger.warning(f"  - Fallback: using all {len(eligible_instrs)} instructors")
                
                # Don't skip the subject - continue with fallback eligibility
                subjects_without_options.append((code, f"{reason} (used fallback)"))
                # Don't increment subjects_skipped_count since we're using fallback
            
            # Get options for this subject
            subj_opts = all_start_options.get(subject_id, [])
            if not subj_opts:
                logger.warning(f"Subject {code} ({subject_id}) has no valid time windows - generating fallback options")
                logger.warning(f"  - Subject type: {getattr(subject, 'subject_type', '?')}")
                logger.warning(f"  - Subject code: {getattr(subject, 'code', '?')}")
                logger.warning(f"  - Hours LEC: {getattr(subject, 'hours_lec', 0)}, LAB: {getattr(subject, 'hours_lab', 0)}")
                logger.warning(f"  - Available days: {list(slots_by_day.keys())}")
                
                # FALLBACK: Generate basic time windows for this subject
                subj_opts = _generate_fallback_time_windows(subject, slots_by_day, days, logger)
                
                if subj_opts:
                    logger.warning(f"  - Generated {len(subj_opts)} fallback time windows")
                    # Add these to the global options for this subject
                    all_start_options[subject_id] = subj_opts
                else:
                    logger.error(f"  - Could not generate any fallback time windows - subject will be unschedulable")
                    subjects_without_options.append((code, "no valid time windows (fallback failed)"))
                    subjects_skipped_count += 1
                    continue
            
            # Track which days have compatible rooms/instructors
            day_compatibility = defaultdict(lambda: {"rooms": 0, "instructors": 0, "options_created": 0})
            
            # Track total variables created for this subject
            subject_var_count = 0
            options_processed = 0
            
            skipped_student_conflict = 0
            skipped_no_rooms = 0
            skipped_no_instructors = 0
            
            # Track if we've logged filtering for this subject (log once per subject on first window)
            logged_filtering_for_subject = False
            
            # CRITICAL: Store original eligible lists - these should NOT be modified in the filtering loop
            # The filtering loop only reads from eligible_rooms/eligible_instrs and builds compatible_rooms/compatible_instructors
            original_eligible_rooms_for_verification = list(eligible_rooms)
            original_eligible_instrs_for_verification = list(eligible_instrs)
            
            # For each option, check room/instructor compatibility and create CP variables
            # OPTIMIZED: Early termination when we have enough good options
            MIN_VIABLE_OPTIONS = 50  # Stop processing once we have this many viable options
            for opt_idx, opt in enumerate(subj_opts):
                # Detailed debug logging for FIRST subject in cluster 0, FIRST window only
                is_first_window_detailed = (should_log_detailed and opt_idx == 0)
                # Safety check: stop creating variables if we've exceeded the limit
                if subject_var_count >= MAX_VARIABLES_PER_SUBJECT:
                    logger.warning(
                        "Subject %d (%s): Stopped creating variables at limit (%d). "
                        "Remaining %d options skipped.",
                        subject_id, code, MAX_VARIABLES_PER_SUBJECT,
                        len(subj_opts) - opt_idx
                    )
                    break
                # OPTIMIZED: Early termination when we have enough viable options
                # This avoids processing all 285+ time positions when 50 good ones exist
                if subject_var_count >= MIN_VIABLE_OPTIONS and opt_idx > len(subj_opts) // 3:
                    logger.debug(
                        "Subject %d (%s): Early termination at %d viable options (processed %d/%d time slots).",
                        subject_id, code, subject_var_count, opt_idx, len(subj_opts)
                    )
                    break
                options_processed = opt_idx + 1
                
                # Handle multi-day options (MW, TTh) vs single-day options
                if "day_ids" in opt:
                    # Multi-day option (MW, TTh)
                    day_ids = opt["day_ids"]
                    day_labels = opt.get("days", [])
                else:
                    # Single-day option (backward compatibility)
                    day_ids = [opt["day_id"]]
                    day_labels = [opt.get("day", "?")]
                
                # Primary day_id for backward compatibility (use first day)
                day_id = day_ids[0]
                start_min = opt["start_min"]
                end_min = opt["end_min"]
                duration_min = opt["duration_min"]
                block_indices = set(opt.get("block_indices", opt.get("slot_indexes", [])))  # Use block_indices if available

                # Cross-cluster student conflict prevention (minute-range based).
                # If another cluster already scheduled something for the same cohort (year + student_block)
                # on this day, we must not allow overlapping intervals.
                try:
                    subj_year_val = getattr(subject, "year_level", None) or default_year
                    subj_year_int = int(subj_year_val) if subj_year_val is not None else int(default_year)
                except Exception:
                    subj_year_int = int(default_year) if default_year is not None else 0

                try:
                    subj_block_idx = int(getattr(subject, "student_block", 1) or 1)
                except Exception:
                    subj_block_idx = 1

                option_conflicts_students = False
                for d_id in day_ids:
                    for existing_start, existing_end in cross_cluster_scheduled_ranges.get((subj_year_int, subj_block_idx, int(d_id)), []):
                        if _ranges_overlap(int(start_min), int(end_min), int(existing_start), int(existing_end)):
                            option_conflicts_students = True
                            break
                    if option_conflicts_students:
                        break

                if option_conflicts_students:
                    skipped_student_conflict += 1
                    continue
                
                # Detailed debug logging for first subject in cluster 0, first window
                if is_first_window_detailed:
                    logger.debug("DEBUG - Block indices for window: %s (days: %s)", sorted(list(block_indices)), day_labels)
                    # Log sample room availability
                    if eligible_rooms:
                        sample_room_id = eligible_rooms[0]
                        for d_id in day_ids:
                            sample_available = room_available_blocks.get(sample_room_id, {}).get(d_id, set())
                            logger.debug("DEBUG - Room available blocks for ROOMID %d on DAY %d: %s (total: %d blocks)",
                                       sample_room_id, d_id, sorted(list(sample_available))[:20], len(sample_available))
                    # Log sample instructor availability
                    if eligible_instrs:
                        sample_instr_id = eligible_instrs[0]
                        for d_id in day_ids:
                            sample_instr_available = instructor_available_blocks.get(sample_instr_id, {}).get(d_id, set())
                            logger.debug("DEBUG - Instructor available blocks for INSTRUCTORID %d on DAY %d: %s (total: %d blocks)",
                                       sample_instr_id, d_id, sorted(list(sample_instr_available))[:20], len(sample_instr_available))
                
                # Pre-filter rooms: use precomputed available blocks with per-day checks
                # CRITICAL: Use blocks_by_day for accurate per-day availability checking
                compatible_rooms = []
                blocks_by_day = opt.get("blocks_by_day", {})
                if not blocks_by_day:
                    # Fallback: construct from block_indices if blocks_by_day missing
                    blocks_by_day = {d_id: block_indices for d_id in day_ids}
                
                for room_id in eligible_rooms:
                    room_name = room_id_to_name.get(room_id)
                    if room_name is None:
                        continue
                    
                    # Capacity check (per-subject enrollment)
                    room = room_by_id.get(room_id)
                    if room and room.capacity and hasattr(subject, 'enrollment'):
                        if room.capacity < getattr(subject, 'enrollment', 0):
                            continue
                    
                    # Check availability for every day in the option
                    room_ok = True
                    for d_id in day_ids:
                        # Range-based conflict check (handles overlapping TIME_BLOCK definitions)
                        if _range_conflicts(booked_room_ranges_global, room_name, d_id, start_min, end_min):
                            room_ok = False
                            break
                        available_blocks = room_available_blocks.get(room_id, {}).get(d_id, set())
                        required_blocks = blocks_by_day.get(d_id, block_indices)  # Fallback to union if missing
                        # Ensure *all* required blocks for that day are available
                        if not required_blocks.issubset(available_blocks):
                            room_ok = False
                            break
                    
                    if room_ok:
                        compatible_rooms.append((room_id, room_name))
                
                # Log room filtering results (once per subject, on first window)
                if is_first_window_detailed:
                    logger.debug("DEBUG - Compatible rooms AFTER filtering: %d", len(compatible_rooms))
                elif not logged_filtering_for_subject:
                    logger.debug(
                        "Subject %d (%s) window %d: Compatible rooms AFTER filtering: %d (from %d eligible)",
                        subject_id, code, opt_idx, len(compatible_rooms), len(eligible_rooms)
                    )
                
                # Track room compatibility per day (update for all days in option)
                for d_id in day_ids:
                    day_compatibility[d_id]["rooms"] = max(day_compatibility[d_id]["rooms"], len(compatible_rooms))
                
                # CRITICAL: Skip window if no compatible rooms - prevents creating variables without rooms
                # This is essential - CP-SAT requires room assignments for proper constraint modeling
                if not compatible_rooms:
                    # Safety assert to catch any bypass logic that might create instructor-only variables
                    # If this assert fails, it means compatible_rooms was modified or bypassed elsewhere
                    assert len(compatible_rooms) == 0, "BUG: Window passed room filtering without rooms - check for instructor-only variable creation"
                    skipped_no_rooms += 1
                    continue
                
                # Pre-filter instructors: use precomputed available blocks with per-day checks
                # CRITICAL: Mirror room logic - check instructor_available_blocks[instr_id][day] for each day_id
                compatible_instructors = []
                for instructor_id in eligible_instrs:
                    # Check availability for every day in the option
                    instr_ok = True
                    for d_id in day_ids:
                        # Range-based conflict check (handles overlapping TIME_BLOCK definitions)
                        if _range_conflicts(booked_instr_ranges_global, instructor_id, d_id, start_min, end_min):
                            instr_ok = False
                            break
                        available_blocks = instructor_available_blocks.get(instructor_id, {}).get(d_id, set())
                        required_blocks = blocks_by_day.get(d_id, block_indices)  # Fallback to union if missing
                        # Ensure *all* required blocks for that day are available
                        if not required_blocks.issubset(available_blocks):
                            instr_ok = False
                            break
                    
                    if not instr_ok:
                        continue
                    
                    compatible_instructors.append(instructor_id)
                
                # Log instructor filtering results (once per subject, on first window)
                if is_first_window_detailed:
                    logger.debug("DEBUG - Compatible instructors AFTER filtering: %d", len(compatible_instructors))
                    first_subject_in_cluster_0_logged = True  # Mark as logged - only log first subject
                elif not logged_filtering_for_subject:
                    logger.debug(
                        "Subject %d (%s) window %d: Compatible instructors AFTER filtering: %d (from %d eligible)",
                        subject_id, code, opt_idx, len(compatible_instructors), len(eligible_instrs)
                    )
                    logged_filtering_for_subject = True  # Mark as logged
                
                # Track instructor compatibility per day (update for all days in option)
                for d_id in day_ids:
                    day_compatibility[d_id]["instructors"] = max(day_compatibility[d_id]["instructors"], len(compatible_instructors))
                
                if not compatible_instructors:
                    skipped_no_instructors += 1
                    continue
                
                # OPTIMIZED: Cap large sets to prevent variable explosion while maintaining schedulability
                # Target: max 9 combinations per time option (3 rooms × 3 instructors)
                # This provides ~10x speedup vs original while avoiding unscheduled subjects
                MAX_ROOMS_PER_OPTION = 5
                MAX_INSTRUCTORS_PER_OPTION = 5
                MAX_COMBINATIONS_PER_OPTION = 14
                
                # Cap rooms and instructors to prevent exponential explosion
                if len(compatible_rooms) > MAX_ROOMS_PER_OPTION:
                    # Prioritize rooms by capacity (prefer larger rooms for flexibility)
                    compatible_rooms.sort(key=lambda r: room_by_id.get(r[0], type('obj', (object,), {'capacity': 0})).capacity or 0, reverse=True)
                    compatible_rooms = compatible_rooms[:MAX_ROOMS_PER_OPTION]
                
                if len(compatible_instructors) > MAX_INSTRUCTORS_PER_OPTION:
                    # Prioritize instructors (could use teaching load, availability, etc.)
                    # For now, just take first N (they're already filtered by availability)
                    compatible_instructors = compatible_instructors[:MAX_INSTRUCTORS_PER_OPTION]
                
                # Additional safety: if we still have too many combinations, further reduce
                total_combinations = len(compatible_rooms) * len(compatible_instructors)
                if total_combinations > MAX_COMBINATIONS_PER_OPTION:
                    # Reduce to target by proportionally scaling down
                    scale_factor = (MAX_COMBINATIONS_PER_OPTION / total_combinations) ** 0.5
                    new_room_count = max(1, int(len(compatible_rooms) * scale_factor))
                    new_instr_count = max(1, int(len(compatible_instructors) * scale_factor))
                    compatible_rooms = compatible_rooms[:new_room_count]
                    compatible_instructors = compatible_instructors[:new_instr_count]
                
                # FINAL SAFETY CHECK: Ensure compatible_rooms is not empty before creating variables
                # This prevents creating instructor-only variables (which would break CP-SAT room constraints)
                if not compatible_rooms or len(compatible_rooms) == 0:
                    logger.error(
                        "[CRITICAL BUG] Subject %d (%s) window %d: Attempted to create variables with empty compatible_rooms! "
                        "This should have been caught earlier. Skipping variable creation.",
                        subject_id, code, opt_idx
                    )
                    continue
                
                # Create CP variables for compatible combinations
                # Both room and instructor loops are required - no instructor-only variables
                for room_id, room_name in compatible_rooms:
                    for instructor_id in compatible_instructors:
                        # CRITICAL: Create ONE presence variable per option (shared across all days)
                        # This ensures all days in a multi-day option (MW, TTh) are scheduled together
                        # Use primary day_id for the presence variable key (backward compatibility)
                        start_var_key = (subject_id, day_id, start_min, opt_idx, room_id, instructor_id)
                        presence = model.NewBoolVar(f"opt_s{subject_id}_d{day_id}_t{start_min}_n{opt_idx}_r{room_id}_i{instructor_id}")
                        start_presence_map[start_var_key] = presence
                        try:
                            presence_weekly_minutes[start_var_key] = int(duration_min) * int(len(day_ids) or 1)
                        except Exception:
                            presence_weekly_minutes[start_var_key] = 0

                        instructor_presence_terms[instructor_id].append(
                            (presence, int(presence_weekly_minutes.get(start_var_key, 0)))
                        )
                        
                        # CRITICAL: Create separate interval for EACH day in day_ids
                        # MW options create 2 intervals (Monday + Wednesday)
                        # TTh options create 2 intervals (Tuesday + Thursday)
                        # F options create 1 interval (Friday)
                        # LAB options create 1 interval (single day)
                        for d_id in day_ids:
                            # Get per-day block indices if available
                            day_block_indices = blocks_by_day.get(d_id, block_indices)
                            
                            # Create interval key for this specific day
                            day_interval_key = (subject_id, d_id, start_min, opt_idx, room_id, instructor_id)
                            
                            # Create optional interval for this day with fixed start/end and shared presence
                            interval = model.NewOptionalIntervalVar(
                                start_min, duration_min, end_min, presence,
                                f"int_s{subject_id}_d{d_id}_t{start_min}_n{opt_idx}_r{room_id}_i{instructor_id}"
                            )
                            start_interval_map[day_interval_key] = interval
                            
                            # Store metadata for this day (for constraints and output)
                            start_metadata[day_interval_key] = {
                                "blocks_spanned": opt["blocks_spanned"],
                                "block_indices": day_block_indices,  # Per-day block indices
                                "start_min": start_min,
                                "end_min": end_min,
                                "duration_min": duration_min,
                                "room_id": room_id,
                                "room_name": room_name,
                                "instructor_id": instructor_id,
                                "day_id": d_id,  # Specific day for this interval
                                "day_ids": day_ids,  # All days in this option
                                "slot_indexes": opt["slot_indexes"],
                                "slot_labels": opt["slot_labels"],
                            }
                        
                        # Keep backward compatibility: create old-style start_vars and start_covers
                        # Use primary day_id for backward compatibility
                        global_start = opt["slot_indexes"][0] if opt["slot_indexes"] else 0
                        num_slots = opt["num_slots"]
                        old_key = (subject_id, room_id, global_start, instructor_id, num_slots)
                        start_vars[old_key] = presence
                        
                        # Build time label
                        slot_labels = opt["slot_labels"]
                        if len(slot_labels) == 1:
                            time_label = slot_labels[0]
                        else:
                            time_label = f"{slot_labels[0].split('–')[0]}–{slot_labels[-1].split('–')[-1]}"
                        
                        # Store covers with all day_ids for multi-day options
                        start_covers[old_key] = {
                            "time_label": time_label,
                            "day_id": day_id,  # Primary day for backward compatibility
                            "day_ids": day_ids,  # All days in this option
                            "start_min": start_min,
                            "end_min": end_min,
                            "start_block_index": opt["slot_indexes"][0] if opt["slot_indexes"] else 0,
                            "end_block_index": opt["slot_indexes"][-1] if opt["slot_indexes"] else 0,
                            "block_indices": block_indices,
                            "slot_indexes": opt["slot_indexes"],  # Store list for easy iteration
                            "duration_min": duration_min,
                            "first_block_id": min(opt["blocks_spanned"]) if opt["blocks_spanned"] else None,
                            "last_block_id": max(opt["blocks_spanned"]) if opt["blocks_spanned"] else None,
                            "blocks_spanned": opt["blocks_spanned"],
                            "room_name": room_name,
                            "slot_labels": opt["slot_labels"],  # Store for safe reconstruction
                        }
                        
                        start_options_count[subject_id] += 1
                        # Track options created for all days in this option
                        for d_id in day_ids:
                            day_compatibility[d_id]["options_created"] += 1
                        subject_var_count += 1
            
            # Log variable creation summary
            if subject_var_count > 0:
                logger.info(
                    "Subject %d (%s): Created %d CP variables (limit: %d). "
                    "Time options processed: %d/%d",
                    subject_id, code, subject_var_count, MAX_VARIABLES_PER_SUBJECT,
                    options_processed, len(subj_opts)
                )
            else:
                logger.warning(
                    "Subject %d (%s): Created 0 CP variables. options=%d processed=%d "
                    "eligible_rooms=%d eligible_instrs=%d skipped_student_conflict=%d skipped_no_rooms=%d skipped_no_instructors=%d",
                    subject_id,
                    code,
                    len(subj_opts),
                    options_processed,
                    len(eligible_rooms),
                    len(eligible_instrs),
                    skipped_student_conflict,
                    skipped_no_rooms,
                    skipped_no_instructors,
                )
            
            # VERIFICATION: Ensure eligible lists were not modified during filtering
            if eligible_rooms != original_eligible_rooms_for_verification:
                logger.error(
                    "BUG: eligible_rooms was modified during filtering! "
                    "Original: %s, Current: %s",
                    original_eligible_rooms_for_verification, eligible_rooms
                )
            if eligible_instrs != original_eligible_instrs_for_verification:
                logger.error(
                    "BUG: eligible_instrs was modified during filtering! "
                    "Original: %s, Current: %s",
                    original_eligible_instrs_for_verification, eligible_instrs
                )
            
            # Log day compatibility summary for first subject only
            if subject_id == subject_ids_list[0] if subject_ids_list else False:
                logger.info(f"Subject {subject_id} ({code}) day compatibility:")
                for day_id in sorted(day_compatibility.keys()):
                    compat = day_compatibility[day_id]
                    logger.info(f"  Day {day_id}: {compat['rooms']} rooms, {compat['instructors']} instructors, {compat['options_created']} CP vars")
        
        # Track which subjects have variables for which days
        subject_days = defaultdict(set)  # subject_id -> {day_id, ...}
        for (sid, r, s, i, dur), var in start_vars.items():
            covers = start_covers[(sid, r, s, i, dur)]
            day_id = covers["day_id"]
            subject_days[sid].add(day_id)
        # Also check new format variables
        for (sid, day_id, start_min, opt_idx, room_id, instructor_id) in start_presence_map.keys():
            subject_days[sid].add(day_id)

        subject_instructor_ids = defaultdict(set)
        for (sid, r, s, i, dur) in start_vars.keys():
            subject_instructor_ids[sid].add(i)
        instructor_choice_vars = {}
        for sid, instr_ids in subject_instructor_ids.items():
            instr_list = sorted(instr_ids)
            instr_var = model.NewIntVarFromDomain(
                cp_model.Domain.FromValues(instr_list),
                f"instr_choice_s{sid}"
            )
            instructor_choice_vars[sid] = instr_var

            # Enforce that all CP variables for this subject share the same instructor
            for (sid2, r, s, i, dur), var in start_vars.items():
                if sid2 != sid:
                    continue
                model.Add(instr_var == i).OnlyEnforceIf(var)

            # NEW: If a global instructor has already been chosen for this
            # (code, course, year) in a previous cluster, force reuse here.
            subject_obj = subject_lookup_cluster.get(sid)
            if subject_obj:
                subj_code = (getattr(subject_obj, "code", "") or "").upper().strip()
                if subj_code:
                    subj_course_id = getattr(subject_obj, "course_id", None) or course_id
                    subj_year = getattr(subject_obj, "year_level", None) or default_year
                    try:
                        key_year = int(subj_year) if subj_year is not None else int(default_year)
                    except (TypeError, ValueError):
                        key_year = int(default_year) if default_year is not None else 0
                    try:
                        key_block = int(getattr(subject_obj, "student_block", 1) or 1)
                    except Exception:
                        key_block = 1
                    gkey = (subj_code, int(subj_course_id), key_year, key_block)
                    if gkey in global_lec_instr_by_key:
                        global_instr = global_lec_instr_by_key[gkey]
                        if global_instr in instr_list:
                            # Reuse the globally chosen instructor when compatible with eligibility.
                            model.Add(instr_var == global_instr)
                        else:
                            # If the global instructor is not eligible for this subject in this cluster,
                            # log a warning but do NOT enforce the equality. This avoids making the
                            # cluster infeasible just to preserve cross-cluster reuse.
                            logger.warning(
                                "Global LEC/LAB instructor %s for %s (course=%s, year=%s) "
                                "not in eligible list %s for subject ID %s; skipping reuse in this cluster.",
                                global_instr, subj_code, subj_course_id, key_year, instr_list, sid,
                            )
        
        total_start_vars = len(start_vars)
        nonzero = sum(1 for sid in subject_ids_list if start_options_count[sid] > 0)
        
        # Calculate theoretical max vars (before filtering) for comparison
        # This helps track how effective the pre-filtering is
        theoretical_max = 0
        for subject_id in subject_ids_list:
            subject = subject_lookup_cluster.get(subject_id)
            if not subject:
                continue
            # CRITICAL: Maps are now keyed by subject.id, not course_id
            eligible_rooms = course_to_rooms.get(subject_id, [])
            if not isinstance(eligible_rooms, list):
                eligible_rooms = list(eligible_rooms) if eligible_rooms else []
            
            eligible_instrs = course_to_instructors.get(subject_id, [])
            if not isinstance(eligible_instrs, list):
                eligible_instrs = list(eligible_instrs) if eligible_instrs else []
            
            # CRITICAL: Use len() > 0 check, NOT truthy check
            if len(eligible_instrs) > 0 and len(eligible_rooms) > 0:
                # Rough estimate: subjects × rooms × instructors × days × slot_positions × durations
                num_days = len(days)
                avg_slots_per_day = sum(len(slots_by_day.get(d.label, [])) for d in days) // max(1, num_days)
                slot_counts = list(range(
                    subject.min_slots or subject.recommended_slots or 1,
                    (subject.max_slots or subject.recommended_slots or 1) + 1
                ))
                theoretical_max += len(eligible_instrs) * len(eligible_rooms) * num_days * avg_slots_per_day * len(slot_counts)
        
        reduction_pct = ((theoretical_max - total_start_vars) / max(1, theoretical_max)) * 100 if theoretical_max > 0 else 0
        logger.info(
            "Built start options: total_vars=%d (theoretical_max=~%d, reduction=%.1f%%), "
            "subjects_with_options=%d/%d, subjects_skipped=%d",
            total_start_vars, theoretical_max, reduction_pct, nonzero, len(subject_ids_list), subjects_skipped_count
        )
        
        if total_start_vars == 0:
            logger.warning("No start options for cluster %s — skipping.", cluster_id)
            if subjects_without_options:
                # Group by reason for better reporting
                by_reason = defaultdict(list)
                for code, reason in subjects_without_options:
                    by_reason[reason].append(code)
                for reason, codes in by_reason.items():
                    logger.warning("  Skipped %d subjects due to %s: %s", 
                                 len(codes), reason, ", ".join(codes[:10]) + ("..." if len(codes) > 10 else ""))
            # Log some diagnostic info
            logger.warning("Cluster %s: %d subjects, %d codes with instructors, %d codes with rooms, "
                          "%d days, %d total slots", 
                          cluster_id, len(cluster_subjects),
                          len(course_to_instructors), len(course_to_rooms),
                          len(days), sum(len(slots) for slots in slots_by_day.values()))
            continue
        
        # Selected boolean per subject: whether subject is scheduled
        selected = {}
        for subject_id in subject_ids_list:
            selected[subject_id] = model.NewBoolVar(f"sel_{subject_id}")
            # NEW APPROACH: Get all presence variables for this subject
            all_presences = [
                p for k, p in start_presence_map.items() 
                if k[0] == subject_id
            ]
            if all_presences:
                # Allow subject to be unscheduled (selected=0) OR scheduled with exactly one option (selected=1).
                # This avoids making an entire cluster infeasible when two subjects cannot both be placed.
                model.Add(sum(all_presences) == selected[subject_id])
            else:
                model.Add(selected[subject_id] == 0)
        
        # Create CP variables for each subject to choose a START time block
        # Subjects can span multiple consecutive blocks based on their duration
        # block_id represents a time window (e.g., block_id 1 = 07:30-09:00), not a subject property
        subject_start_block_vars = {}  # subject_id -> IntVar (selected start_block_id)
        subject_duration_blocks = {}  # subject_id -> int (how many consecutive blocks needed)
        
        for subject_id in subject_ids_list:
            subject = subject_lookup_cluster.get(subject_id)
            if not subject:
                continue
            
            # Calculate how many time blocks this subject needs
            # Each time block is 30 minutes (1 slot of 30 minutes)
            rec_slots = subject.recommended_slots or subject.min_slots or 1
            min_slots = subject.min_slots or rec_slots
            max_slots = subject.max_slots or rec_slots
            
            # Convert slots to blocks: Since each block = 1 slot (30 minutes), conversion is 1:1
            # 1 slot = 1 block, 2 slots = 2 blocks, etc.
            max_blocks_needed = max_slots
            min_blocks_needed = min_slots
            
            # Store duration for this subject (we'll use the actual duration from the assignment)
            subject_duration_blocks[subject_id] = (min_blocks_needed, max_blocks_needed)
            
            # Each subject can choose a start block_id
            # Valid start blocks: those where start_block_id + duration_blocks - 1 <= max_block_id
            valid_start_blocks = [
                bid for bid in time_block_ids
                if bid + min_blocks_needed - 1 <= max_block_id
            ]
            
            if valid_start_blocks:
                subject_start_block_vars[subject_id] = model.NewIntVarFromDomain(
                    cp_model.Domain.FromValues(valid_start_blocks),
                    f"subj_{subject_id}_start_block"
                )
        
        # Constraint: If subject is scheduled, it must fit within consecutive blocks starting from start_block_id
        # Use precomputed block spans from start_covers (no loops during CP construction)
        for (sid, r, s, i, dur), var in start_vars.items():
            covers = start_covers[(sid, r, s, i, dur)]
            first_block_id = covers.get("first_block_id")
            
            if not first_block_id or sid not in subject_start_block_vars:
                # Skip if we can't map to blocks or subject has no start_block variable
                continue
            
            subject_start_block_var = subject_start_block_vars[sid]
            
            # OPTIMIZED: Constraint is already tight - OnlyEnforceIf provides optimal propagation
            # If assignment is active, start_block_id must equal first_block_id
            # This constraint is already optimally formulated for CP-SAT
            model.Add(subject_start_block_var == first_block_id).OnlyEnforceIf(var)
        
        logger.debug("Created start_block selection variables for %d subjects", len(subject_start_block_vars))
        
        # ====================================================================
        # CONSTRAINT GROUP 1: Room Conflict Prevention (using CP-SAT Intervals)
        # Rule: No two classes in the same room can overlap in time on the same day
        # ====================================================================
        # Precompute grouping maps BEFORE creating intervals (no loops during CP construction)
        # Use precomputed subject_lookup_cluster from above (line 700)
        room_intervals_by_resource = defaultdict(list)  # (room_name, day_id) -> [(var, start_min, duration_min, end_min), ...]
        instr_intervals_by_resource = defaultdict(list)  # (instr_id, day_id) -> [(var, start_min, duration_min, end_min), ...]
        student_intervals_by_resource = defaultdict(list)  # (course_id, year_level, day_id) -> [(var, start_min, duration_min, end_min), ...]
        
        # Precompute all interval data and grouping in one pass (no loops during CP construction)
        var_to_interval_data = {}  # var -> (start_min, duration_min, end_min, room_name, instr_id, course_id, year_level, day_id)
        
        # FIXED: Group variables by subject first, then by cohort
        # This ensures we create one interval per subject, not one per CP variable
        subject_vars_by_cohort = defaultdict(lambda: defaultdict(list))  # (course_id, year_level, student_block_index, day_id) -> subject_id -> [(var, start_min, duration_min, end_min), ...]
        
        # CRITICAL: Also build cross-cluster grouping by (year_level, student_block_index, day_id)
        # This groups subjects across ALL clusters that share the same year_level, student block, and day
        cross_cluster_vars_by_group = defaultdict(lambda: defaultdict(list))  # (year_level, student_block_index, day_id) -> subject_id -> [(var, start_min, duration_min, end_min), ...]
        
        # IMPORTANT: start_vars/start_covers can be lossy due to key collisions.
        # Build hard constraints from authoritative start_metadata + start_presence_map.
        for (sid, day_id, start_min, opt_idx, room_id, instructor_id), meta in start_metadata.items():
            # Presence var is keyed by PRIMARY day_id. For multi-day patterns, meta["day_ids"][0] is the primary.
            day_ids_all = meta.get("day_ids") or [day_id]
            primary_day_id = day_ids_all[0] if day_ids_all else day_id
            presence_key = (sid, primary_day_id, start_min, opt_idx, room_id, instructor_id)
            var = start_presence_map.get(presence_key)
            if var is None:
                continue

            room_name = meta.get("room_name") or room_id_to_name.get(room_id)

            # start_metadata is already per-day, so we only add constraints for THIS day_id.
            start_min = meta.get("start_min")
            end_min = meta.get("end_min")
            duration_min = meta.get("duration_min")
            if start_min is None or end_min is None or duration_min is None:
                continue

            # Precomputed subject lookup (no linear search)
            subject = subject_lookup_cluster.get(sid)
            subj_course_id = course_id
            year_level = default_year
            student_block_index = 1
            if subject:
                subj_course_id = subject.course_id or course_id
                year_level = subject.year_level or default_year
                try:
                    student_block_index = getattr(subject, "student_block", 1)
                except Exception:
                    student_block_index = 1
            
            try:
                student_block_index = int(student_block_index)
            except (TypeError, ValueError):
                student_block_index = 1

            # --- normalize keys to ints to avoid dict-key mismatches ---
            subj_year = subject.year_level if subject and getattr(subject, "year_level", None) is not None else default_year
            try:
                subj_year = int(subj_year)
            except (TypeError, ValueError):
                subj_year = int(default_year)
            
            # ensure day_id is an int
            try:
                day_id_int = int(day_id)
            except (TypeError, ValueError):
                logger.warning("Non-int day_id encountered when grouping vars: %r", day_id)
                day_id_int = int(day_id) if day_id is not None else 0

            # Store for interval creation (one entry per day)
            var_to_interval_data[var] = (start_min, duration_min, end_min, room_name, instructor_id, subj_course_id, year_level, day_id_int)

            # Precompute grouping maps - group by (resource, day_id) for each day separately
            if room_name:
                room_intervals_by_resource[(room_name, day_id_int)].append((var, start_min, duration_min, end_min))

            instr_intervals_by_resource[(instructor_id, day_id_int)].append((var, start_min, duration_min, end_min))

            # FIXED: Group by subject within cohort (course_id, year_level, student_block, day_id)
            cohort_key = (subj_course_id, year_level, student_block_index, day_id_int)
            subject_vars_by_cohort[cohort_key][sid].append((var, start_min, duration_min, end_min))

            # Cross-cluster student conflicts depend ONLY on (year_level, student_block_index, day_id)
            cross_cluster_key = (subj_year, student_block_index, day_id_int)
            cross_cluster_vars_by_group[cross_cluster_key][sid].append((var, start_min, duration_min, end_min))
        
        # OPTIMIZED: Only create intervals when needed (2+ variables for NoOverlap)
        # NoOverlap constraints only matter when there are multiple intervals
        room_interval_vars = {}  # (room_name, day_id) -> [interval_vars]
        room_no_overlap_count = 0
        for (room_name, day_id), var_data_list in room_intervals_by_resource.items():
            # Only create intervals if there are 2+ variables (NoOverlap requires multiple intervals)
            if len(var_data_list) <= 1:
                continue
            
            intervals = []
            for var, start_min, duration_min, end_min in var_data_list:
                interval_name = f"room_intv_{var.Name()}"
                interval = model.NewOptionalIntervalVar(
                    start_min, duration_min, end_min, var, interval_name
                )
                intervals.append(interval)
            room_interval_vars[(room_name, day_id)] = intervals
            
            # Add NoOverlap constraint (we know len(intervals) > 1)
            model.AddNoOverlap(intervals)
            room_no_overlap_count += 1
        
        logger.debug(f"Added {room_no_overlap_count} room NoOverlap constraints")
        
        # ====================================================================
        # CONSTRAINT GROUP 2: Instructor Conflict Prevention (using CP-SAT Intervals)
        # Rule: A single instructor cannot teach overlapping classes
        # ====================================================================
        # OPTIMIZED: Only create intervals when needed (2+ variables for NoOverlap)
        instr_interval_vars = {}  # (instr_id, day_id) -> [interval_vars]
        instr_no_overlap_count = 0
        for (instr_id, day_id), var_data_list in instr_intervals_by_resource.items():
            # Only create intervals if there are 2+ variables (NoOverlap requires multiple intervals)
            if len(var_data_list) <= 1:
                continue
            
            intervals = []
            for var, start_min, duration_min, end_min in var_data_list:
                interval_name = f"instr_intv_{var.Name()}"
                interval = model.NewOptionalIntervalVar(
                    start_min, duration_min, end_min, var, interval_name
                )
                intervals.append(interval)
            instr_interval_vars[(instr_id, day_id)] = intervals
            
            # Add NoOverlap constraint (we know len(intervals) > 1)
            model.AddNoOverlap(intervals)
            instr_no_overlap_count += 1
        
        logger.debug(f"Added {instr_no_overlap_count} instructor NoOverlap constraints")
        
        # ====================================================================
        # CONSTRAINT GROUP 3: Student Conflict Prevention (using CP-SAT Intervals)
        # Rule: Within the same course, year_level, and student block, no overlapping
        #       times for that cohort on a given day.
        # Note: block_id now represents time blocks (time windows), not student sections.
        # ====================================================================
        
        # FIXED: Build student_intervals_by_resource from subject-grouped data
        # Group: (course_id, year_level, day_id) -> list of intervals (one per subject)
        student_intervals_by_resource = defaultdict(list)  # (course_id, year_level, day_id) -> [interval_vars]
        
        # Create one interval per subject (not per variable)
        # For each subject, create an interval that represents ANY of its possible assignments
        # Use the selected[subject_id] variable to control which interval is active
        for cohort_key, subjects_dict in subject_vars_by_cohort.items():
            course_id_key, year_level_key, student_block_key, day_id = cohort_key
            
            # Only process cohorts with 2+ subjects (need multiple subjects for conflict detection)
            if len(subjects_dict) <= 1:
                continue
            
            intervals = []
            for subject_id, var_data_list in subjects_dict.items():
                # For each subject, create a single interval that represents the subject's assignment
                # We need to create an interval that spans the time range of whichever variable is selected
                # Since we can't know which variable will be selected, we create intervals for all possibilities
                # but link them to the subject's selected variable
                
                # Create intervals for each possible assignment of this subject
                for var, start_min, duration_min, end_min in var_data_list:
                    # CRITICAL: Validate duration calculation
                    calculated_duration = end_min - start_min
                    if abs(duration_min - calculated_duration) > 1:  # Allow 1 minute tolerance for rounding
                        logger.warning(f"[INTERVAL BUG] Subject {subject_id}: duration mismatch! "
                                     f"Stored duration_min={duration_min} vs calculated={calculated_duration} "
                                     f"(start_min={start_min}, end_min={end_min})")
                        # Use the correct calculated duration
                        duration_min = calculated_duration
                    
                    # Only create interval if this variable could be active
                    # The interval is optional - it's only active if var == 1
                    interval_name = f"student_intv_s{subject_id}_{var.Name()}"
                    interval = model.NewOptionalIntervalVar(
                        start_min, duration_min, end_min, var, interval_name
                    )
                    intervals.append(interval)
            
            if intervals:
                student_intervals_by_resource[cohort_key] = intervals
        
        # OPTIMIZED: Only create intervals when needed (2+ subjects for NoOverlap/Cumulative)
        student_interval_vars = {}  # (course_id, year_level, day_id) -> [interval_vars]
        student_no_overlap_count = 0
        
        for (course_id_key, year_level_key, student_block_key, day_id), intervals in student_intervals_by_resource.items():
            # Only create constraints if there are 2+ intervals (need multiple subjects for conflict)
            if len(intervals) <= 1:
                continue
            
            student_interval_vars[(course_id_key, year_level_key, student_block_key, day_id)] = intervals
        
        # Enforce no overlaps within same course/year_level and day
        # Note: block_capacity_overrides key format is (course_id, year_level, block_id)
        # But block_id now refers to time blocks, so we need to handle this differently
        for (course_id_key, year_level_key, student_block_key, day_id), intervals in student_interval_vars.items():
            # For now, use capacity=1 (no overlaps) by default
            # TODO: Support block_capacity_overrides with time block awareness
            capacity = 1
            # Try to get capacity override - check all time blocks for this course/year
            for block_id in time_block_ids:
                override_key = (course_id_key, year_level_key, block_id)
                if override_key in block_capacity_overrides:
                    cap = block_capacity_overrides[override_key]
                    if cap is not None:
                        capacity = max(capacity, max(0, int(cap)))
            
            if capacity <= 0:
                # No capacity => forbid all assignments
                # Get vars from precomputed var_data_list
                for var, _, _, _ in student_intervals_by_resource.get((course_id_key, year_level_key, student_block_key, day_id), []):
                    model.Add(var == 0)
                continue
            
            if capacity == 1:
                # Simple case: no overlaps allowed - use AddNoOverlap
                if len(intervals) > 1:
                    model.AddNoOverlap(intervals)
                    student_no_overlap_count += 1
            else:
                # Capacity > 1: Use AddCumulative to enforce capacity constraint
                if len(intervals) > 1:
                    demands = [1] * len(intervals)
                    model.AddCumulative(intervals, demands, capacity)
                    student_no_overlap_count += 1
        
        logger.info(
            "Added %d student conflict NoOverlap/Cumulative constraints across %d course-year-block-day combinations",
            student_no_overlap_count,
            len(student_intervals_by_resource),
        )

        enforce_global_slot_exclusivity = False
        if enforce_global_slot_exclusivity:
            global_slot_groups = defaultdict(list)  # (course_id, year_level, day_id, start_min, end_min) -> [vars]
            for var, data in var_to_interval_data.items():
                try:
                    start_min, duration_min, end_min, room_name, instr_id, c_id_val, y_level_val, day_id_val = data
                except Exception:
                    continue
                if start_min is None or end_min is None or day_id_val is None:
                    continue
                try:
                    day_id_int = int(day_id_val)
                    course_id_int = int(c_id_val) if c_id_val is not None else None
                    year_level_int = int(y_level_val) if y_level_val is not None else None
                except (TypeError, ValueError):
                    continue
                if course_id_int is None or year_level_int is None:
                    continue
                global_slot_groups[(course_id_int, year_level_int, day_id_int, int(start_min), int(end_min))].append(var)

            global_slot_constraints = 0
            for (course_id_int, year_level_int, day_id_int, start_min_val, end_min_val), vars_for_slot in global_slot_groups.items():
                if len(vars_for_slot) <= 1:
                    continue
                model.Add(sum(vars_for_slot) <= 1)
                global_slot_constraints += 1

            if global_slot_constraints > 0:
                logger.info(
                    "Added %d global time-slot exclusivity constraints across all blocks (day_id, start_min, end_min)",
                    global_slot_constraints,
                )

        # ====================================================================
        # CONSTRAINT GROUP 5: Cross-Cluster Student Conflict Prevention
        # Rule: Students in the same year_level cannot have overlapping classes on the same day
        #       regardless of which cluster or course the subjects belong to
        # ====================================================================

        cross_cluster_intervals_by_group = defaultdict(list)  # (year_level, student_block_index, day_id) -> [interval_vars]

        # Add intervals from THIS cluster's variables
        for (year_level_key, student_block_key, day_id), subjects_dict in cross_cluster_vars_by_group.items():
            if len(subjects_dict) <= 1:
                continue

            intervals = []
            subject_codes = []  # for logging
            for subject_id, var_data_list in subjects_dict.items():
                subject_code = id_to_code.get(subject_id, f"ID_{subject_id}")
                subject_codes.append(subject_code)

                # Deduplicate by unique time window (start_min, end_min)
                time_windows = defaultdict(list)
                for var, start_min, duration_min, end_min in var_data_list:
                    # validate duration
                    calc_duration = end_min - start_min
                    if abs(duration_min - calc_duration) > 1:
                        logger.warning(
                            f"[CROSS-CLUSTER INTERVAL BUG] Subject {subject_id} ({subject_code}): "
                            f"duration mismatch! Stored duration_min={duration_min} vs calculated={calc_duration} "
                            f"(start_min={start_min}, end_min={end_min})"
                        )
                        duration_min = calc_duration
                    time_windows[(start_min, end_min)].append(var)

                # Create one interval per unique time window
                for (start_min, end_min), vars_for_window in time_windows.items():
                    duration_min = end_min - start_min
                    tw_active = model.NewBoolVar(f"cross_cluster_tw_s{subject_id}_{start_min}_{end_min}")

                    if len(vars_for_window) == 1:
                        model.Add(tw_active == vars_for_window[0])
                    else:
                        model.AddMaxEquality(tw_active, vars_for_window)

                    interval_name = f"cross_cluster_intv_s{subject_id}_tw{start_min}_{end_min}"
                    interval = model.NewOptionalIntervalVar(start_min, duration_min, end_min, tw_active, interval_name)
                    intervals.append(interval)

            if intervals:
                cross_cluster_intervals_by_group[(year_level_key, student_block_key, day_id)].extend(intervals)
                logger.debug(
                    f"[CROSS-CLUSTER] Group (year={year_level_key}, block={student_block_key}, day={day_id}): "
                    f"{len(subjects_dict)} subjects ({', '.join(subject_codes[:5])}{'...' if len(subject_codes) > 5 else ''}), "
                    f"{len(intervals)} intervals (deduplicated from room×instructor combinations)"
                )

        # Add fixed intervals from previously scheduled clusters
        for (year_level_key_raw, student_block_key_raw, day_id_raw), scheduled_ranges in cross_cluster_scheduled_ranges.items():
            try:
                year_level_key = int(year_level_key_raw)
            except (TypeError, ValueError):
                year_level_key = int(default_year)
            try:
                student_block_key = int(student_block_key_raw)
            except (TypeError, ValueError):
                student_block_key = 1
            try:
                day_id_key = int(day_id_raw)
            except (TypeError, ValueError):
                day_id_key = int(day_id_raw) if day_id_raw is not None else 0

            for start_min, end_min in scheduled_ranges:
                duration_min = end_min - start_min
                fixed_var = model.NewBoolVar(f"cross_cluster_fixed_{year_level_key}_{day_id_key}_{start_min}")
                model.Add(fixed_var == 1)
                interval_name = f"cross_cluster_fixed_intv_{year_level_key}_{day_id_key}_{start_min}"
                interval = model.NewOptionalIntervalVar(start_min, duration_min, end_min, fixed_var, interval_name)
                cross_cluster_intervals_by_group[(year_level_key, student_block_key, day_id_key)].append(interval)

        # Apply NoOverlap constraints for cross-cluster groups
        cross_cluster_no_overlap_count = 0
        for (year_level_key, student_block_key, day_id), intervals in cross_cluster_intervals_by_group.items():
            if len(intervals) <= 1:
                continue
            model.AddNoOverlap(intervals)
            cross_cluster_no_overlap_count += 1

            subject_ids_in_group = set()
            for interval_name in [iv.Name() for iv in intervals]:
                if "_s" in interval_name:
                    try:
                        parts = interval_name.split("_s")[1].split("_")
                        if parts:
                            subject_ids_in_group.add(int(parts[0]))
                    except (ValueError, IndexError):
                        pass
            subject_codes_in_group = [id_to_code.get(sid, f"ID_{sid}") for sid in sorted(subject_ids_in_group)[:5]]
            logger.info(
                f"[CROSS-CLUSTER] Added NoOverlap for (year={year_level_key}, block={student_block_key}, day={day_id}): "
                f"{len(intervals)} intervals covering {len(subject_ids_in_group)} subjects "
                f"({', '.join(subject_codes_in_group)}{'...' if len(subject_codes_in_group) > 5 else ''}) "
                f"(includes {len(cross_cluster_scheduled_ranges.get((year_level_key, student_block_key, day_id), []))} fixed from previous clusters)"
            )

        if cross_cluster_no_overlap_count > 0:
            logger.info(
                "[CROSS-CLUSTER] Added %d cross-cluster student conflict NoOverlap constraints "
                "(year_level, day_id) grouping - PRIMARY protection against overlaps",
                cross_cluster_no_overlap_count
            )
        else:
            logger.warning("[CROSS-CLUSTER] WARNING: No cross-cluster constraints added! "
                        "This may allow overlaps between subjects with different course_id values.")

        # ====================================================================
        # CONSTRAINT GROUP 5: Day Distribution (cluster-level hints)
        # ====================================================================
        subject_day_vars = defaultdict(lambda: defaultdict(list))
        band_day_vars = defaultdict(lambda: defaultdict(list))
        for (sid, r, s, i, dur), var in start_vars.items():
            covers = start_covers.get((sid, r, s, i, dur), {})
            day_ids = covers.get("day_ids") or [covers.get("day_id")]
            day_ids = [d for d in day_ids if d is not None]
            start_min = covers.get("start_min")
            for day_id in day_ids:
                try:
                    day_id_int = int(day_id)
                except (TypeError, ValueError):
                    continue
                subject_day_vars[sid][day_id_int].append(var)
                if start_min is not None:
                    for band in TIME_BANDS:
                        if band["min"] <= start_min < band["max"]:
                            band_day_vars[band["label"]][day_id_int].append(var)
                            break

        day_target_penalties = []
        distribution_penalty = None
        if subject_day_vars:
            day_ids_list = [d.id for d in days]
            cluster_day_counts = []
            max_day_count = max(1, len(subject_ids_list))
            for day_id in day_ids_list:
                day_vars = []
                for sid in subject_ids_list:
                    day_vars.extend(subject_day_vars[sid].get(day_id, []))
                if not day_vars:
                    continue
                count_var = model.NewIntVar(0, len(day_vars), f"cluster_{cluster_id}_count_day_{day_id}")
                model.Add(count_var == sum(day_vars))
                # NOTE: Hard per-day load bounds (DAY_LOAD_HARD_MIN/MAX) are removed to
                # maximize feasibility. Day balancing is now handled purely via soft
                # penalties (DAY_LOAD_TARGET_MIN/MAX) in the objective.
                cluster_day_counts.append(count_var)

                # Soft penalty deltas: allow any feasible count_var value (including 0)
                # without constraining the schedule.
                lower_delta = model.NewIntVar(-max_day_count, DAY_LOAD_TARGET_MIN, f"day_{day_id}_lower_delta")
                upper_delta = model.NewIntVar(-DAY_LOAD_TARGET_MAX, max_day_count, f"day_{day_id}_upper_delta")
                model.Add(lower_delta == DAY_LOAD_TARGET_MIN - count_var)
                model.Add(upper_delta == count_var - DAY_LOAD_TARGET_MAX)
                under_pen = model.NewIntVar(0, DAY_LOAD_TARGET_MIN, f"day_{day_id}_under_pen")
                over_pen = model.NewIntVar(0, max_day_count, f"day_{day_id}_over_pen")
                model.AddMaxEquality(under_pen, [model.NewConstant(0), lower_delta])
                model.AddMaxEquality(over_pen, [model.NewConstant(0), upper_delta])
                target_pen = model.NewIntVar(0, DAY_LOAD_TARGET_MIN + max_day_count, f"day_{day_id}_target_pen")
                model.Add(target_pen == under_pen + over_pen)
                day_target_penalties.append(target_pen)

            if cluster_day_counts:
                max_cluster_day = model.NewIntVar(0, max_day_count, f"cluster_{cluster_id}_max_day")
                min_cluster_day = model.NewIntVar(0, max_day_count, f"cluster_{cluster_id}_min_day")
                for count_var in cluster_day_counts:
                    model.Add(max_cluster_day >= count_var)
                    model.Add(min_cluster_day <= count_var)
                cluster_day_balance_penalty = model.NewIntVar(0, max_day_count, f"cluster_{cluster_id}_day_penalty")
                model.Add(cluster_day_balance_penalty == max_cluster_day - min_cluster_day)
                distribution_penalty = cluster_day_balance_penalty

        early_penalty_terms = []
        for opt_key, var in start_vars.items():
            start_min = start_covers.get(opt_key, {}).get("start_min")
            if start_min is None:
                continue
            penalty_value = max(0, EARLY_THRESHOLD_MIN - start_min)
            if penalty_value > 0:
                early_penalty_terms.append(penalty_value * var)

        band_penalty_terms = []
        time_band_total_penalty = model.NewIntVar(
            0,
            len(TIME_BANDS) * DAY_LOAD_HARD_MAX * max(1, len(subject_ids_list)) * 2,
            f"cluster_{cluster_id}_time_band_penalty",
        )
        for band in TIME_BANDS:
            band_label = band["label"]
            band_vars = [var for vars_by_day in band_day_vars.get(band_label, {}).values() for var in vars_by_day]
            band_count = model.NewIntVar(0, len(band_vars) if band_vars else DAY_LOAD_HARD_MAX * len(subject_ids_list), f"band_{band_label}_count")
            if band_vars:
                model.Add(band_count == sum(band_vars))
            else:
                model.Add(band_count == 0)
            min_req = band.get("min_count", 0)
            max_req = band.get("max_count", DAY_LOAD_HARD_MAX * len(subject_ids_list))

            # IMPORTANT: These are soft constraints only. The helper variable domains must
            # be wide enough to represent any feasible band_count value, otherwise they
            # accidentally become hard constraints for small clusters.
            band_scale = max(
                DAY_LOAD_HARD_MAX * max(1, len(subject_ids_list)),
                int(min_req) if min_req is not None else 0,
                int(max_req) if max_req is not None else 0,
            )
            lower_delta = model.NewIntVar(-band_scale, band_scale, f"band_{band_label}_lower_delta")
            upper_delta = model.NewIntVar(-band_scale, band_scale, f"band_{band_label}_upper_delta")
            model.Add(lower_delta == min_req - band_count)
            model.Add(upper_delta == band_count - max_req)
            under_pen = model.NewIntVar(0, band_scale, f"band_{band_label}_under_pen")
            over_pen = model.NewIntVar(0, band_scale, f"band_{band_label}_over_pen")
            model.AddMaxEquality(under_pen, [model.NewConstant(0), lower_delta])
            model.AddMaxEquality(over_pen, [model.NewConstant(0), upper_delta])
            band_pen = model.NewIntVar(0, band_scale * 2, f"band_{band_label}_pen")
            model.Add(band_pen == under_pen + over_pen)
            band_penalty_terms.append(band_pen)
        if band_penalty_terms:
            model.Add(time_band_total_penalty == sum(band_penalty_terms))
        else:
            model.Add(time_band_total_penalty == 0)

        # Soft day-of-week preferences:
        # - For codes that have BOTH LEC and LAB (paired subjects):
        #   LEC options prefer MW/TTh (penalize Friday-only patterns).
        # - For LEC subjects with NO LAB counterpart: prefer Friday-only (penalize MW/TTh).
        # - For all LAB subjects: prefer Mon–Thu (penalize Friday).
        day_pref_penalty_terms = []
        for (sid, r, s, i, dur), var in start_vars.items():
            covers = start_covers.get((sid, r, s, i, dur), {})
            day_labels = covers.get("days") or []
            if not day_labels:
                continue
            subject_obj = subject_lookup_cluster.get(sid)
            subj_type = (getattr(subject_obj, "type", "") or "").upper().strip() if subject_obj else ""
            subj_code = (getattr(subject_obj, "code", "") or "").upper().strip() if subject_obj else ""
            penalty_value = 0

            if subj_type == "LEC":
                # Under the new rule, all LEC subjects (with or without LAB counterparts)
                # must use MW/TTh patterns and should not be penalized for MW/TTh.
                # We only penalize Friday-only patterns, which are now effectively
                # disabled for LEC in option generation but kept here for safety.
                if "F" in day_labels and len(day_labels) == 1:
                    penalty_value = 1
            elif subj_type == "LAB":
                # Avoid Friday for LABs (prefer Mon–Thu)
                if "F" in day_labels:
                    penalty_value = 1

            if penalty_value > 0:
                day_pref_penalty_terms.append(penalty_value * var)

        day_pref_total_penalty = model.NewIntVar(
            0,
            max(1, len(start_vars)) * 2,
            f"cluster_{cluster_id}_day_pref_penalty",
        )
        if day_pref_penalty_terms:
            model.Add(day_pref_total_penalty == sum(day_pref_penalty_terms))
        else:
            model.Add(day_pref_total_penalty == 0)

        early_penalty_var = model.NewIntVar(0, len(start_vars) * EARLY_THRESHOLD_MIN, f"cluster_{cluster_id}_early_penalty")
        if early_penalty_terms:
            model.Add(early_penalty_var == sum(early_penalty_terms))
        else:
            model.Add(early_penalty_var == 0)

        # Primary objective: maximize the number of scheduled subjects with penalties for imbalance
        scheduled_sum = sum(selected.values())

        major_ids = []
        unmarked_ids = []
        minor_ids = []
        for sid in subject_ids_list:
            subj = subject_lookup.get(sid)
            v = getattr(subj, "is_major", None) if subj is not None else None
            if v is True:
                major_ids.append(sid)
            elif v is False:
                minor_ids.append(sid)
            else:
                unmarked_ids.append(sid)

        major_sum = sum(selected[sid] for sid in major_ids) if major_ids else 0
        unmarked_sum = sum(selected[sid] for sid in unmarked_ids) if unmarked_ids else 0
        minor_sum = sum(selected[sid] for sid in minor_ids) if minor_ids else 0

        # Build objective combining subject count with soft penalties. The
        # SCHEDULE_REWARD_WEIGHT is intentionally large so that, when a
        # feasible assignment exists, the solver prefers scheduling as many
        # subjects as possible rather than dropping subjects just to reduce
        # soft penalties (day balance, time bands, early/late preferences).
        penalty_exprs = []
        if day_target_penalties:
            total_day_target_penalty = model.NewIntVar(
                0,
                len(day_target_penalties) * (DAY_LOAD_TARGET_MIN + max(1, len(subject_ids_list))),
                f"cluster_{cluster_id}_day_target_total"
            )
            model.Add(total_day_target_penalty == sum(day_target_penalties))
            penalty_exprs.append(DAY_TARGET_PENALTY_WEIGHT * total_day_target_penalty)
        penalty_exprs.append(TIME_BAND_PENALTY_WEIGHT * time_band_total_penalty)
        penalty_exprs.append(DAY_PREF_PENALTY_WEIGHT * day_pref_total_penalty)
        if distribution_penalty is not None:
            penalty_exprs.append(DAY_TARGET_PENALTY_WEIGHT * distribution_penalty)

        overload_penalty_terms = []
        zero_var = model.NewIntVar(0, 0, f"cluster_{cluster_id}_zero")
        for inst_id in instructor_ids:
            inst_terms = []
            inst_coeff_sum = 0
            for var, coeff in instructor_presence_terms.get(inst_id, []):
                if coeff:
                    inst_terms.append(int(coeff) * var)
                    inst_coeff_sum += int(coeff)
            if not inst_terms:
                continue
            current_min = int(instructor_current_minutes.get(inst_id, 0))
            limit_min = int(instructor_limit_minutes.get(inst_id, 24 * 60))
            assigned_min_var = model.NewIntVar(0, max(0, inst_coeff_sum), f"cluster_{cluster_id}_inst_{inst_id}_assigned_min")
            model.Add(assigned_min_var == sum(inst_terms))
            total_min_var = model.NewIntVar(0, max(0, current_min + inst_coeff_sum), f"cluster_{cluster_id}_inst_{inst_id}_total_min")
            model.Add(total_min_var == assigned_min_var + current_min)
            diff_min_var = model.NewIntVar(-max(0, limit_min), max(0, current_min + inst_coeff_sum), f"cluster_{cluster_id}_inst_{inst_id}_diff_min")
            model.Add(diff_min_var == total_min_var - limit_min)
            over_min_ub = max(0, current_min + inst_coeff_sum - limit_min)
            over_min_var = model.NewIntVar(0, over_min_ub, f"cluster_{cluster_id}_inst_{inst_id}_over_min")
            model.AddMaxEquality(over_min_var, [zero_var, diff_min_var])
            overload_penalty_terms.append(over_min_var)

        overload_penalty_weight = 5
        if overload_penalty_terms:
            penalty_exprs.append(overload_penalty_weight * sum(overload_penalty_terms))

        major_reward = int(SCHEDULE_REWARD_WEIGHT) * 100000
        minor_reward = int(SCHEDULE_REWARD_WEIGHT) * 100
        unmarked_reward = int(SCHEDULE_REWARD_WEIGHT)
        max_reward = max(major_reward, unmarked_reward, minor_reward)

        objective_expr = (
            major_sum * major_reward
            + minor_sum * minor_reward
            + unmarked_sum * unmarked_reward
            - EARLY_PENALTY_WEIGHT * early_penalty_var
        )
        if penalty_exprs:
            objective_expr -= sum(penalty_exprs)
        # Bounds are deliberately wide to accommodate the large reward weight.
        objective_var = model.NewIntVar(
            -len(subject_ids_list) * max_reward * 10,
            len(subject_ids_list) * max_reward * 10,
            f"cluster_{cluster_id}_objective"
        )
        model.Add(objective_var == objective_expr)
        model.Maximize(objective_var)

        # ====================================================================
        subjects_by_code = defaultdict(lambda: {"LEC": [], "LAB": []})
        for subject in cluster_subjects:
            code = (subject.code or "").upper().strip()
            subj_type = (subject.type or "").upper().strip()
            if subj_type in ("LEC", "LAB"):
                subjects_by_code[code][subj_type].append(subject)

        lec_lab_pairing_count = 0
        for code, type_subjects in subjects_by_code.items():
            lec_subjects = type_subjects.get("LEC", [])
            lab_subjects = type_subjects.get("LAB", [])
            if not lec_subjects or not lab_subjects:
                continue

            for lec_subj in lec_subjects:
                for lab_subj in lab_subjects:
                    # Collect all CP vars for these subjects keyed by day
                    lec_by_day = defaultdict(list)
                    lab_by_day = defaultdict(list)
                    for (sid, r, s, i, dur), var in start_vars.items():
                        if sid not in (lec_subj.id, lab_subj.id):
                            continue
                        covers = start_covers.get((sid, r, s, i, dur), {})
                        day_ids = covers.get("day_ids") or [covers.get("day_id")]
                        day_ids = [d for d in day_ids if d is not None]
                        for day_id in day_ids:
                            if sid == lec_subj.id:
                                lec_by_day[day_id].append((var, covers))
                            else:
                                lab_by_day[day_id].append((var, covers))

                    if not lec_by_day or not lab_by_day:
                        continue

                    # 1) Ensure both LEC and LAB are scheduled (if either is scheduled)
                    all_lec_vars = [v for vars_covers in lec_by_day.values() for (v, _) in vars_covers]
                    all_lab_vars = [v for vars_covers in lab_by_day.values() for (v, _) in vars_covers]
                    if not all_lec_vars or not all_lab_vars:
                        continue
                    lec_scheduled = model.NewBoolVar(f"lec_{lec_subj.id}_scheduled")
                    lab_scheduled = model.NewBoolVar(f"lab_{lab_subj.id}_scheduled")
                    model.Add(sum(all_lec_vars) >= 1).OnlyEnforceIf(lec_scheduled)
                    model.Add(sum(all_lec_vars) == 0).OnlyEnforceIf(lec_scheduled.Not())
                    model.Add(sum(all_lab_vars) >= 1).OnlyEnforceIf(lab_scheduled)
                    model.Add(sum(all_lab_vars) == 0).OnlyEnforceIf(lab_scheduled.Not())
                    model.AddBoolOr([lec_scheduled.Not(), lab_scheduled])
                    model.AddBoolOr([lab_scheduled.Not(), lec_scheduled])

                    lec_instr_var = instructor_choice_vars.get(lec_subj.id)
                    lab_instr_var = instructor_choice_vars.get(lab_subj.id)
                    if lec_instr_var is not None and lab_instr_var is not None:
                        model.Add(lec_instr_var == lab_instr_var)

                    # 2) Prefer different days: forbid both on the *same* day when there
                    #    exists at least one alternative day for each.
                    common_days = set(lec_by_day.keys()) & set(lab_by_day.keys())
                    for day_id in common_days:
                        # If there is only this day for one of them, skip (no choice).
                        if len(lec_by_day) == 1 or len(lab_by_day) == 1:
                            continue
                        lec_vars_this_day = [v for (v, _) in lec_by_day[day_id]]
                        lab_vars_this_day = [v for (v, _) in lab_by_day[day_id]]
                        if not lec_vars_this_day or not lab_vars_this_day:
                            continue
                        # Sum of all lec vars on this day + all lab vars on this day <= 1
                        # i.e., they cannot *both* choose this day simultaneously.
                        model.Add(sum(lec_vars_this_day) + sum(lab_vars_this_day) <= 1)

                    # 3) Within any day, still avoid LEC/LAB overlaps
                    for day_id in common_days:
                        lec_vars_with_covers = lec_by_day.get(day_id, [])
                        lab_vars_with_covers = lab_by_day.get(day_id, [])
                        for lec_var, lec_covers in lec_vars_with_covers:
                            lec_start = lec_covers.get("start_min")
                            lec_end = lec_covers.get("end_min")
                            if lec_start is None or lec_end is None:
                                continue
                            for lab_var, lab_covers in lab_vars_with_covers:
                                lab_start = lab_covers.get("start_min")
                                lab_end = lab_covers.get("end_min")
                                if lab_start is None or lab_end is None:
                                    continue
                                overlaps = not (lec_end <= lab_start or lab_end <= lec_start)
                                if overlaps:
                                    model.AddBoolOr([lec_var.Not(), lab_var.Not()])

                    lec_lab_pairing_count += 1

        if lec_lab_pairing_count > 0:
            logger.info(f"Added {lec_lab_pairing_count} LEC/LAB pairing constraints (distinct-day preference + no overlap)")
        # LEC/LAB LINKING ENDS HERE

        
        hint_count = 0
        hinted_subjects = 0
        
        # Only add hints for subjects with very few options (≤ 2)
        # These are the most constrained cases where hints are most valuable
        for subject_id in subject_ids_list:
            starts_for_s = [v for (sid, *_), v in start_vars.items() if sid == subject_id]
            num_options = len(starts_for_s)
            
            # Only hint for subjects with ≤ 2 options (highly constrained)
            if num_options > 2:
                continue
            
            if num_options == 0:
                continue
            
            # Find the best hint for this subject from greedy hints
            best_var = None
            best_hint_key = None
            
            # Look for matching hints in greedy_hints
            if greedy_hints:
                for key, val in greedy_hints.items():
                    hint_subject_id = key[0]
                    if hint_subject_id != subject_id:
                        continue
                    
                    # Check if this hint matches a valid variable
                    var = start_vars.get(key)
                    if var is None:
                        # Try alternative durations
                        room_id, start_idx, instructor_id, dur = key[1:]
                        for alt_dur in [dur - 1, dur + 1, dur]:
                            if alt_dur < 1:
                                continue
                            alt_key = (subject_id, room_id, start_idx, instructor_id, alt_dur)
                            var = start_vars.get(alt_key)
                            if var:
                                break
                    
                    if var and var in starts_for_s:
                        # Prefer hints with value 1 (greedy found a solution)
                        if val == 1 or best_var is None:
                            best_var = var
                            best_hint_key = key
                            if val == 1:
                                break  # Found perfect match, use it
            
            # If no greedy hint found, use the first available variable
            if best_var is None and starts_for_s:
                best_var = starts_for_s[0]
            
            # Add hint for this highly constrained subject
            if best_var is not None:
                try:
                    model.AddHint(best_var, 1)  # Hint: prefer this variable
                    hint_count += 1
                    hinted_subjects += 1
                except Exception as e:
                    logger.debug("AddHint failed for subject %s: %s", subject_id, e)
        
        if hint_count > 0:
            logger.info("Applied selective partial hints: %d hints for %d highly constrained subjects (≤2 options) in cluster %s",
                       hint_count, hinted_subjects, cluster_id)
        
        # Solver configuration & solve
        solver = cp_model.CpSolver()
        # Adjust max time based on cluster size - larger clusters get more time
        cluster_size = len(cluster_subjects)
        if cluster_size > 50:
            cluster_max_time = min(max_time_seconds * 2.0, 300.0)  # Up to 5 minutes for large clusters
        elif cluster_size > 20:
            cluster_max_time = min(max_time_seconds * 1.5, 180.0)  # Up to 3 minutes for medium clusters
        else:
            cluster_max_time = min(max_time_seconds, 300.0)  # Standard time for small clusters
        
        solver.parameters.max_time_in_seconds = cluster_max_time
        # OPTIMIZED: Fewer workers often faster for CP-SAT due to less synchronization overhead
        solver.parameters.num_search_workers = max(1, min(4, os.cpu_count() or 1))
        solver.parameters.random_seed = 9
        
        # OPTIMIZED: Use AUTOMATIC_SEARCH which adapts to problem structure
        # This is faster than PORTFOLIO_SEARCH for most scheduling problems
        solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        solver.parameters.log_search_progress = False
        
        # OPTIMIZED: Minimal linearization for speed (scheduling is mostly boolean)
        solver.parameters.linearization_level = 0
        
        # OPTIMIZED: Minimal probing for speed - probing is expensive and the variable
        # reduction already ensures a small search space
        solver.parameters.cp_model_probing_level = 0
        solver.parameters.cp_model_presolve = True
        
        # OPTIMIZED: Early stopping - accept solutions within 5% of optimal
        # This dramatically speeds up convergence while maintaining quality
        solver.parameters.relative_gap_limit = 0.05
        solver.parameters.absolute_gap_limit = 1
        
        # Note: use_sat_presolver, polish_lp_solution, and cp_model_use_sat_inprocessing
        # are not available or deprecated in OR-Tools 9.8 - removed for compatibility
        
        # OPTIMIZED: Strong decision strategy for large boolean search spaces
        # CHOOSE_MIN_DOMAIN_SIZE produces strong propagation and is supported in OR-Tools 9.8
        # This is more effective than CHOOSE_FIRST for large problems
        # NOTE: start_vars is a backward-compatibility map that can be lossy due to key collisions.
        # Use start_presence_map for authoritative branching over all option variables.
        all_start_vars_list = list(start_presence_map.values())
        if all_start_vars_list:
            model.AddDecisionStrategy(
                all_start_vars_list,
                cp_model.CHOOSE_MIN_DOMAIN_SIZE,  # Strong propagation strategy (replacement for removed CHOOSE_HIGHEST_MAX_ACTIVITY)
                cp_model.SELECT_MAX_VALUE  # Select max value (1 for boolean = active)
            )
        
        # Allow optimization: stopping after the first feasible solution can leave
        # subjects unscheduled even when a better (higher objective) solution exists.
        solver.parameters.stop_after_first_solution = False
        
        import time
        solve_start = time.time()
        
        # Report progress for solver phase
        report_progress(f"🧮 Solving cluster {cluster_id}: {total_start_vars} variables...")
        
        logger.info("Running solver for cluster %s (vars=%d, max_time=%.1fs)...", cluster_id, total_start_vars, cluster_max_time)
        status = solver.Solve(model)
        solve_elapsed = time.time() - solve_start
        logger.info("Solver status: %s (took %.1fs)", solver.StatusName(status), solve_elapsed)
        
        # Debug infeasibility
        if status == cp_model.INFEASIBLE:
            logger.warning("Model is INFEASIBLE for cluster %s. Exporting model for debugging...", cluster_id)
            try:
                debug_file = f"infeasible_cluster{cluster_id}.txt"
                solver.ExportModelAsLp(debug_file)
                logger.warning("Exported infeasible model to %s", debug_file)
            except Exception as e:
                logger.debug("Could not export model: %s", e)
        
        # Log solver statistics
        if hasattr(solver, 'NumBranches'):
            logger.info("Solver stats: branches=%d, conflicts=%d, wall_time=%.2fs",
                       solver.NumBranches(), solver.NumConflicts(), solve_elapsed)
        
                # Collect scheduled items and update global bookings
        scheduled_rows = []
        # Track scheduled assignments for conflict detection
        scheduled_by_subject = {}  # subject_id -> row (to detect duplicates)
        scheduled_by_resource = defaultdict(list)  # (resource_type, resource_id, day_id, block_index) -> [rows]
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Build an index from a selected presence key -> all per-day metadata rows.
            # This avoids O(n^2) scans across start_metadata.
            meta_by_presence_key = defaultdict(list)
            for (sid2, _d_id2, start_min2, opt_idx2, room_id2, instructor_id2), meta in start_metadata.items():
                meta_by_presence_key[(sid2, start_min2, opt_idx2, room_id2, instructor_id2)].append(meta)

            # DEBUG: Track which days are actually selected by solver.
            selected_days = defaultdict(int)  # day_id -> count
            for (subject_id, _day_id, start_min, opt_idx, room_id, instructor_id), presence in start_presence_map.items():
                if not solver.BooleanValue(presence):
                    continue
                for meta in meta_by_presence_key.get((subject_id, start_min, opt_idx, room_id, instructor_id), []):
                    try:
                        selected_days[int(meta.get("day_id"))] += 1
                    except Exception:
                        continue

            if selected_days:
                logger.info(f"Solver selected days: {dict(selected_days)}")

            # Extract scheduled assignments from authoritative presence vars.
            for (subject_id, primary_day_id, start_min, opt_idx, room_id, instructor_id), presence in start_presence_map.items():
                if not solver.BooleanValue(presence):
                    continue

                subject = subject_lookup.get(subject_id)

                # BUG FIX 2: Ensure subject_id is consistent type (int)
                try:
                    clone_subject_id = int(subject_id) if subject_id is not None else None
                except Exception:
                    clone_subject_id = None
                if clone_subject_id is None:
                    logger.error(f"[EXTRACTION BUG] Invalid subject_id in CP variable: {subject_id} (type: {type(subject_id)})")
                    continue

                # Map back to original subject and block index for external output.
                original_subject_id = clone_subject_id
                student_block_index = 1
                if subject is not None:
                    # Prefer original_subject_id when present (per-block clones). For normal
                    # subjects, original_subject_id will typically be None.
                    orig_id = getattr(subject, "original_subject_id", None)
                    if orig_id is not None:
                        try:
                            original_subject_id = int(orig_id)
                        except Exception:
                            original_subject_id = clone_subject_id
                    else:
                        original_subject_id = int(clone_subject_id)

                    try:
                        student_block_index = int(getattr(subject, "student_block", 1) or 1)
                    except Exception:
                        student_block_index = 1
                block_label = _block_index_to_label(student_block_index)

                # ---- NEW SAFE LOGIC (for rewritten start options) ----
                # CRITICAL: Handle multi-day options (MW, TTh) - create rows for ALL days
                # Single-day options (F, LAB) have day_ids = [day_id]
                per_day_metas = meta_by_presence_key.get((subject_id, start_min, opt_idx, room_id, instructor_id), [])

                if not per_day_metas:
                    # Fallback: build a minimal meta from the primary day if metadata is unexpectedly missing.
                    per_day_metas = [{
                        "day_id": primary_day_id,
                        "start_min": start_min,
                        "room_id": room_id,
                        "room_name": room_id_to_name.get(room_id),
                        "instructor_id": instructor_id,
                        "slot_labels": None,
                        "slot_indexes": [],
                        "block_indices": [],
                        "blocks_spanned": [],
                        "duration_min": None,
                        "end_min": None,
                    }]

                # Use first day's metadata for room label; we compute time_label per-day later.
                room_name = per_day_metas[0].get("room_name") or room_id_to_name.get(room_id)

                # --- Resolve start_block_id and end_block_id in a robust, solver-driven way ---
                start_block_id = None
                end_block_id = None

                # If there's a subject-level start-block var (rare), read it.
                # But usually start-block is represented inside the option (covers) or per-option var.
                if subject_id in subject_start_block_vars:
                    try:
                        start_block_id = int(solver.Value(subject_start_block_vars[subject_id]))
                    except Exception as e:
                        logger.debug("Could not read subject_start_block_vars[%s]: %s", subject_id, e)

                # If still None, try to compute block id from start_min via slot_to_block_map (minute -> block_index mapping).
                # slot_to_block_map is expected to be defined earlier (checked in logs: "115/115 slots mapped successfully")
                if start_block_id is None:
                    try:
                        # slot_to_block_map maps (day_id, start_min) -> block_index (or block_id depending on your naming)
                        # Try exact minute lookup first (start_min should be a minute index used earlier)
                        # For multi-day options, try the first day_id
                        first_day_id = per_day_metas[0].get("day_id")
                        if first_day_id is not None:
                            start_block_id_candidate = slot_to_block_map.get((first_day_id, start_min))
                            if start_block_id_candidate is not None:
                                start_block_id = int(start_block_id_candidate)
                        # If exact mapping not found, try using block_indices from covers (deterministic)
                        if start_block_id is None:
                            blocks_spanned = per_day_metas[0].get("blocks_spanned") or per_day_metas[0].get("block_indices") or per_day_metas[0].get("slot_indexes")
                            if blocks_spanned:
                                # blocks_spanned may be a set/list of block indices relative to the day's blocks
                                if isinstance(blocks_spanned, (set, list, tuple)):
                                    # choose the minimum as start, maximum as end
                                    sorted_blocks = sorted(blocks_spanned)
                                    start_block_id = int(sorted_blocks[0])
                                    end_block_id = int(sorted_blocks[-1])
                    except Exception as e:
                        logger.debug("Fallback block id computation failed for subject %s: %s", subject_id, e)

                # If end_block_id still None, compute based on start_block_id + blocks_spanned length (if available)
                if end_block_id is None:
                    blocks_spanned = per_day_metas[0].get("blocks_spanned") or per_day_metas[0].get("block_indices") or per_day_metas[0].get("slot_indexes")
                    if blocks_spanned:
                        try:
                            # blocks_spanned may be number of blocks or list/set of indices
                            if isinstance(blocks_spanned, int):
                                end_block_id = start_block_id + blocks_spanned - 1 if start_block_id is not None else None
                            elif isinstance(blocks_spanned, (list, tuple, set)):
                                end_block_id = int(max(blocks_spanned))
                                # If start_block_id is None, set it to min(blocks_spanned)
                                if start_block_id is None:
                                    start_block_id = int(min(blocks_spanned))
                        except Exception:
                            end_block_id = None

                # As a final fallback, if start_block_id is still None but we have start_min,
                # attempt to infer block index by scanning slot_to_block_map keys (nearest match).
                if start_block_id is None and start_min is not None:
                    try:
                        # Attempt nearest minute match (this is deterministic and safe)
                        first_day_id = per_day_metas[0].get("day_id")
                        if first_day_id is not None:
                            nearest = None
                            min_diff = None
                            for (day_key, minute_key), block_val in slot_to_block_map.items():
                                if day_key == first_day_id:
                                    diff = abs(int(minute_key) - int(start_min))
                                    if min_diff is None or diff < min_diff:
                                        nearest = minute_key
                                        min_diff = diff
                            if nearest is not None:
                                start_block_id = int(slot_to_block_map[(first_day_id, nearest)])
                    except Exception as e:
                        logger.debug("Nearest-block fallback failed for subject %s: %s", subject_id, e)

                # Create reverse mapping for room_name_to_id if not already available
                if 'room_name_to_id' not in locals():
                    room_name_to_id = {name: rid for rid, name in room_id_to_name.items()}

                # --- Build row but DO NOT allow silent defaults ---
                for meta in per_day_metas:
                    day_id = meta.get("day_id")
                    # normalize day_id
                    try:
                        day_id_int = int(day_id)
                    except Exception:
                        logger.error("[EXTRACTION BUG] Invalid day_id for subject %s: %r", subject_id, day_id)
                        continue

                    # Normalize instructor id and room id robustly
                    try:
                        instr_id_int = int(meta.get("instructor_id", instructor_id))
                    except Exception:
                        logger.error("[EXTRACTION BUG] Invalid instructor id for subject %s: %r", subject_id, meta.get("instructor_id", instructor_id))
                        continue

                    # room id may be an int or need mapping (r may be idx->room_id); try to cast
                    try:
                        room_id_int = int(meta.get("room_id", room_id))
                    except Exception:
                        # if r is a name, try to reverse lookup
                        room_id_int = room_name_to_id.get(room_name) if room_name else None

                    if room_id_int is None:
                        logger.error("[EXTRACTION BUG] Missing room id for subject %s (room_id=%r, room_name=%r)", subject_id, room_id, room_name)
                        continue

                    # Ensure start_min/end_min exist for this day (solver-driven)
                    start_min_day = meta.get("start_min")
                    end_min_day = meta.get("end_min")
                    if start_min_day is None or end_min_day is None:
                        logger.error(
                            "[EXTRACTION BUG] Missing start_min/end_min for subject %s (meta=%r)",
                            subject_id,
                            meta,
                        )
                        continue

                    # Canonical time label: prefer the registrar grid label from slots_by_day
                    time_label = None
                    day_label = day_id_to_label.get(day_id_int)
                    if day_label:
                        for slot in slots_by_day.get(day_label, []):
                            try:
                                if int(slot.get("start_min")) == int(start_min_day) and int(slot.get("end_min")) == int(end_min_day):
                                    time_label = slot.get("label")
                                    break
                            except Exception:
                                continue

                    if not time_label:
                        from_minutes = lambda m: f"{m//60}:{str(m%60).zfill(2)}"
                        span_label = f"{from_minutes(int(start_min_day))}–{from_minutes(int(end_min_day))}"
                        time_label = f"{day_label} {span_label}" if day_label else span_label


                    # If end_block_id still None, set it equal to start_block_id (single-block subject)
                    if end_block_id is None:
                        end_block_id = start_block_id

                    # Build the final row now that we validated required fields
                    row = {
                        # External subject identifier: original DB subject ID
                        "subject_id": int(original_subject_id),
                        # Internal clone identifier (per-block synthetic ID) for bookkeeping
                        "clone_subject_id": clone_subject_id,
                        "course_id": subject.course_id if subject else course_id,
                        "instructor_id": instr_id_int,
                        "room_id": room_id_int,
                        "day_id": day_id_int,
                        "time": time_label,
                        "year": subject.year_level if subject and getattr(subject, "year_level", None) else default_year,
                        "semester": subject.semester if subject and getattr(subject, "semester", None) else semester,
                        "block": block_label,
                        "block_id": int(start_block_id),
                        "start_block_id": int(start_block_id),
                        "end_block_id": int(end_block_id),
                        "start_min": int(start_min_day),
                        "end_min": int(end_min_day),
                    }

                    # Duplicate detection (same clone-subject on same day)
                    row_key = (clone_subject_id, day_id_int)
                    if row_key in scheduled_by_subject:
                        existing_row = scheduled_by_subject[row_key]
                        logger.error(
                            "[EXTRACTION BUG] Subject %s scheduled TWICE on day %s by CP! First: %s | Second: %s",
                            subject_id, day_id_int, existing_row, row
                        )
                        continue

                    # Track and append
                    scheduled_by_subject[row_key] = row

                    # Resolve slot_indexes deterministically for conflict detection
                    slot_indexes = meta.get("slot_indexes", [])
                    if not slot_indexes:
                        block_indices = meta.get("block_indices", set())
                        if isinstance(block_indices, set):
                            slot_indexes = sorted(block_indices)
                        else:
                            slot_indexes = list(block_indices) if block_indices else []

                    if not slot_indexes:
                        # create slot_indexes from start_block_id..end_block_id
                        try:
                            slot_indexes = list(range(int(start_block_id), int(end_block_id) + 1))
                        except Exception:
                            slot_indexes = []

                    if not slot_indexes:
                        logger.error("[EXTRACTION BUG] Could not determine slot_indexes for subject %s", subject_id)
                        continue

                    # Deduplicate slot indexes to avoid false conflicts from repeated indices
                    # (e.g., multi-day patterns that reuse the same block index across days)
                    slot_indexes = sorted(set(slot_indexes))

                    for block_index in slot_indexes:
                        scheduled_by_resource[("room", room_name, day_id_int, block_index)].append(row)
                        scheduled_by_resource[("instructor", instr_id_int, day_id_int, block_index)].append(row)

                    scheduled_rows.append(row)

                    try:
                        instr_for_load = int(row.get("instructor_id"))
                        instructor_current_minutes[instr_for_load] += max(0, int(row.get("end_min")) - int(row.get("start_min")))
                    except Exception:
                        pass

                    # Update global bookings
                    for block_index in slot_indexes:
                        booked_room_slots_global.add((room_name, day_id_int, block_index))
                        booked_instr_slots_global.add((instr_id_int, day_id_int, block_index))

                    # Update range-based global bookings
                    booked_room_ranges_global[(room_name, day_id_int)].append((int(start_min_day), int(end_min_day)))
                    booked_instr_ranges_global[(instr_id_int, day_id_int)].append((int(start_min_day), int(end_min_day)))

                    # Update cross-cluster scheduled ranges (normalized)
                    subj_year = subject.year_level if subject and getattr(subject, "year_level", None) else default_year
                    try:
                        subj_year = int(subj_year)
                    except (TypeError, ValueError):
                        subj_year = int(default_year)
                    cross_cluster_scheduled_ranges[(subj_year, student_block_index, day_id_int)].append((int(start_min_day), int(end_min_day)))
        
        # Validate: Check for conflicts in extracted results
        conflicts_found = []
        for (resource_type, resource_id, day_id, block_index), rows in scheduled_by_resource.items():
            if len(rows) > 1:
                conflict_info = {
                    "type": resource_type,
                    "resource_id": resource_id,
                    "day_id": day_id,
                    "block_index": block_index,
                    "subjects": [r["subject_id"] for r in rows],
                    "details": rows
                }
                conflicts_found.append(conflict_info)
                logger.error(f"[EXTRACTION CONFLICT] {resource_type} {resource_id} on day {day_id}, "
                           f"block {block_index} has {len(rows)} assignments: "
                           f"subjects {[r['subject_id'] for r in rows]}")
        
        if conflicts_found:
            logger.error(f"[EXTRACTION BUG] Found {len(conflicts_found)} conflicts in CP extraction! "
                       f"This should NOT happen - CP solver should prevent these.")
        
        # Retry pass: schedule subjects that weren't scheduled by CP
        # BUG FIX 3: Ensure subject IDs are compared as same type (int).
        # IMPORTANT: Use original_subject_id (not clone_subject_id) for tracking scheduled subjects
        scheduled_original_ids = set()
        for row in scheduled_rows:
            oid = row.get("subject_id")  # This is the original subject ID
            if oid is None:
                continue
            try:
                scheduled_original_ids.add(int(oid))
            except Exception:
                continue

        unscheduled_subjects = [
            s
            for s in cluster_subjects
        ]
        # Filter out subjects that were scheduled
        actually_unscheduled = []
        for s in unscheduled_subjects:
            # Get the effective subject ID (original for clones, self for originals)
            # Do NOT use hasattr(student_block) as a clone detector because student_block
            # may exist as a real DB column on all Subject rows.
            eff_id_val = getattr(s, "original_subject_id", None)
            eff_id = eff_id_val if eff_id_val is not None else s.id
            
            if eff_id is not None and int(eff_id) not in scheduled_original_ids:
                actually_unscheduled.append(s)
        
        unscheduled_subjects = actually_unscheduled
        
        # Log retry attempt
        if unscheduled_subjects:
            report_progress(f" Retry pass: scheduling {len(unscheduled_subjects)} remaining subjects...")
            
            logger.info(
                f"[RETRY] Attempting to schedule {len(unscheduled_subjects)} unscheduled subjects: "
                f"{[s.id for s in unscheduled_subjects[:5]]}{'...' if len(unscheduled_subjects) > 5 else ''}"
            )

        # Build combined list of already-scheduled rows across ALL clusters plus
        # the current cluster's CP-scheduled rows so the retry pass can avoid
        # creating student conflicts with existing assignments.
        scheduled_rows_for_retry = []
        if all_scheduled_items:
            scheduled_rows_for_retry.extend(all_scheduled_items)
        if scheduled_rows:
            scheduled_rows_for_retry.extend(scheduled_rows)
        
        retry_results = _retry_unscheduled_subjects(
            db,
            unscheduled_subjects,
            course_to_instructors,
            course_to_rooms,
            slots_by_day,
            booked_room_slots_global,
            booked_instr_slots_global,
            rooms,
            days,
            room_id_to_name,
            course_id,
            default_year,
            semester,
            focus_subject_ids_set,
            global_instr_map=global_lec_instr_by_key,
            scheduled_rows=scheduled_rows_for_retry,  # Pass CP-scheduled subjects for student conflict checking
            booked_room_ranges_global=booked_room_ranges_global,
            booked_instr_ranges_global=booked_instr_ranges_global,
        )
        
        # BUG FIX 3: Validate retry doesn't overwrite CP results for the same subject
        # Compare original subject IDs to avoid double-scheduling
        retry_original_ids = {int(sid) for sid in retry_results.keys()}
        overlap = retry_original_ids & scheduled_original_ids
        if overlap:
            logger.error(f"[RETRY BUG] Retry scheduled {len(overlap)} subjects already scheduled by CP! "
                        f"Overlapping subjects: {overlap}")
            # Remove overlapping subjects from retry results (CP takes precedence)
            # Need to find the original key type in retry_results
            keys_to_remove = []
            for retry_key in retry_results.keys():
                if int(retry_key) in overlap:
                    keys_to_remove.append(retry_key)
            for key in keys_to_remove:
                logger.warning(f"[RETRY BUG] Removing subject {key} from retry results (already scheduled by CP)")
                retry_results.pop(key, None)
        
        # Merge CP results and retry results
        all_scheduled_items.extend(scheduled_rows)
        # Flatten retry_results: values can be dict (single-day) or list (paired multi-day)
        for retry_val in retry_results.values():
            if isinstance(retry_val, list):
                all_scheduled_items.extend(retry_val)
            else:
                all_scheduled_items.append(retry_val)
        
        # Final validation: Check for duplicate subject/day/block combinations in merged results.
        # Multi-day patterns (MW/TTh) legitimately produce multiple rows per subject with
        # different day_ids, so we only treat duplicates for the SAME (subject_id, block, day_id)
        # as bugs (e.g., CP + retry both scheduling same subject+block on same day).
        final_by_subject_day = {}
        final_conflicts = []
        for row in all_scheduled_items:
            try:
                sid = int(row["subject_id"]) if row.get("subject_id") is not None else None
            except Exception:
                sid = None
            block_label_val = row.get("block")
            day_id_val = row.get("day_id")
            try:
                day_id_int = int(day_id_val) if day_id_val is not None else None
            except Exception:
                day_id_int = None

            # If we don't have a valid subject or day, skip duplicate checking for this row
            if sid is None or day_id_int is None:
                continue

            key = (sid, block_label_val, day_id_int)
            if key in final_by_subject_day:
                first = final_by_subject_day[key]
                final_conflicts.append({
                    "subject_id": sid,
                    "day_id": day_id_int,
                    "first": first,
                    "second": row,
                })
                logger.error(
                    "[FINAL CONFLICT] Subject %s appears twice on day %s in final results!",
                    sid,
                    day_id_int,
                )
            else:
                final_by_subject_day[key] = row
        
        if final_conflicts:
            logger.error(
                "[FINAL BUG] Found %d duplicate subject/day entries in final merged results!",
                len(final_conflicts),
            )

        # Update global LEC/LAB instructor map from CP-scheduled rows in this cluster
        for (subject_id, _), row in scheduled_by_subject.items():
            subj = subject_lookup.get(subject_id)
            if not subj:
                continue
            subj_code = (getattr(subj, "code", "") or "").upper().strip()
            if not subj_code:
                continue
            subj_course_id = getattr(subj, "course_id", None) or course_id
            subj_year = getattr(subj, "year_level", None) or default_year
            instr_id = row.get("instructor_id")
            if instr_id is None:
                continue
            try:
                key_year = int(subj_year) if subj_year is not None else int(default_year)
            except (TypeError, ValueError):
                key_year = int(default_year) if default_year is not None else 0
            try:
                key_block = int(getattr(subj, "student_block", 1) or 1)
            except Exception:
                key_block = 1
            gkey = (subj_code, int(subj_course_id), key_year, key_block)
            if gkey in global_lec_instr_by_key and global_lec_instr_by_key[gkey] != instr_id:
                logger.error(
                    "[GLOBAL LEC/LAB INSTR CONFLICT] Subject code %s (course=%s, year=%s, block=%s) has "
                    "conflicting instructors across clusters: %s vs %s",
                    subj_code, subj_course_id, key_year, key_block,
                    global_lec_instr_by_key[gkey], instr_id,
                )
            else:
                global_lec_instr_by_key[gkey] = instr_id

        logger.info("Cluster %s completed: CP scheduled %d, retry scheduled %d, total %d",
                    cluster_id, len(scheduled_rows), len(retry_results), len(scheduled_rows) + len(retry_results))
        
        logger.info("Cluster %s completed: CP scheduled %d, retry scheduled %d, total %d",
                    cluster_id, len(scheduled_rows), len(retry_results), len(scheduled_rows) + len(retry_results))
    
    # ------------------------------------------------------------------
    # GLOBAL FINAL SAFETY NET + POST-CONFLICT RETRY
    # ------------------------------------------------------------------
    logger.info("All clusters completed: total scheduled subjects=%d", len(all_scheduled_items))

    # 1) Global final safety net: detect overlapping subjects per cohort/day
    student_slots_by_key = defaultdict(list)  # (course_id, year, block, day_id) -> [(index, start_min, end_min, row)]
    for idx, row in enumerate(all_scheduled_items):
        c_id = row.get("course_id")
        year_val = row.get("year")
        block_val = row.get("block")
        day_id = row.get("day_id")
        start_min = row.get("start_min")
        end_min = row.get("end_min")
        if c_id and year_val is not None and day_id and start_min is not None and end_min is not None:
            try:
                key = (int(c_id), int(year_val), str(block_val) if block_val is not None else "DEFAULT", int(day_id))
                student_slots_by_key[key].append((idx, int(start_min), int(end_min), row))
            except Exception:
                continue

    subject_ids_to_drop = set()

    for (c_id, year_val, block_key, day_id), entries in student_slots_by_key.items():
        entries_sorted = sorted(entries, key=lambda e: (e[1], e[2]))
        kept = []  # (start_min, end_min, subject_id)
        for idx, start_min, end_min, row in entries_sorted:
            subj_id = row.get("subject_id")
            if subj_id is None:
                continue

            try:
                subj_id_int = int(subj_id)
            except Exception:
                continue

            if subj_id_int in subject_ids_to_drop:
                continue

            overlap = False
            for k_start, k_end, k_subj in kept:
                if not (end_min <= k_start or start_min >= k_end):
                    overlap = True
                    break

            if overlap:
                logger.error(
                    "[FINAL STUDENT CONFLICT] Detected overlap for subject %s (course_id=%s, year=%s) "
                    "on day_id=%s, time=%s with another class in same cohort (no rows dropped).",
                    subj_id_int, c_id, year_val, day_id, row.get("time"),
                )
            else:
                kept.append((start_min, end_min, subj_id_int))

    if subject_ids_to_drop:
        logger.error(
            "[FINAL STUDENT CONFLICT] Dropping %d subjects to enforce no student overlaps: %s",
            len(subject_ids_to_drop), sorted(subject_ids_to_drop),
        )

    # Keep rows for non-conflicting subjects; rows for dropped subjects will
    # be retried in a focused post-conflict pass below.
    kept_rows = [
        row
        for row in all_scheduled_items
        if row.get("subject_id") is None
        or int(row.get("subject_id")) not in subject_ids_to_drop
    ]

    # ------------------------------------------------------------------
    # 2) Post-conflict retry: attempt to reschedule dropped subjects only
    # ------------------------------------------------------------------
    if subject_ids_to_drop:
        try:
            # Rebuild global booking maps from kept rows
            booked_room_slots_retry: Set[Tuple[str, int, int]] = set()
            booked_instr_slots_retry: Set[Tuple[int, int, int]] = set()

            # Build helper maps for day label/id and slot lookup
            day_id_to_label = {d.id: d.label for d in days}

            # Map (day_label, start_min, end_min) -> slot index for lookup
            slot_lookup = {}
            for day in days:
                day_slots = slots_by_day.get(day.label, [])
                for slot in day_slots:
                    key = (day.label, int(slot["start_min"]), int(slot["end_min"]))
                    slot_lookup[key] = slot["index"]

            for row in kept_rows:
                day_id_val = row.get("day_id")
                start_min = row.get("start_min")
                end_min = row.get("end_min")
                room_id = row.get("room_id")
                instr_id = row.get("instructor_id")
                if day_id_val is None or start_min is None or end_min is None:
                    continue
                try:
                    day_id_int = int(day_id_val)
                    start_int = int(start_min)
                    end_int = int(end_min)
                except Exception:
                    continue

                day_label = day_id_to_label.get(day_id_int)
                if not day_label:
                    continue

                # Find matching slots for this time window; if multiple 30m slots,
                # use all indices that cover [start_min, end_min).
                slot_indices = []
                for slot in slots_by_day.get(day_label, []):
                    s_start = int(slot["start_min"])
                    s_end = int(slot["end_min"])
                    if s_start >= start_int and s_end <= end_int:
                        slot_indices.append(slot["index"])

                if not slot_indices:
                    # Fallback: try a direct lookup for the exact window
                    idx = slot_lookup.get((day_label, start_int, end_int))
                    if idx is not None:
                        slot_indices = [idx]

                room_name = room_id_to_name.get(room_id) if room_id is not None else None
                for block_index in slot_indices:
                    if room_name:
                        booked_room_slots_retry.add((room_name, day_id_int, block_index))
                    if instr_id is not None:
                        try:
                            instr_int = int(instr_id)
                        except Exception:
                            instr_int = None
                        if instr_int is not None:
                            booked_instr_slots_retry.add((instr_int, day_id_int, block_index))

            # Build list of dropped Subject objects (per-block clones) to retry
            # We retry at the clone level so multi-block subjects respect block
            # structure, but conflict detection still uses original_subject_id.
            dropped_subjects_to_retry = []
            subject_by_original: Dict[int, List[Any]] = defaultdict(list)
            for subj in subjects:
                try:
                    base_id_val = getattr(subj, "original_subject_id", getattr(subj, "id", None))
                    base_id = int(base_id_val) if base_id_val is not None else None
                except Exception:
                    base_id = None
                if base_id is None:
                    continue
                subject_by_original[base_id].append(subj)

            for dropped_id in subject_ids_to_drop:
                for subj in subject_by_original.get(dropped_id, []):
                    dropped_subjects_to_retry.append(subj)

            if dropped_subjects_to_retry:
                logger.info(
                    "[POST-CONFLICT RETRY] Attempting to reschedule %d dropped subjects: %s",
                    len(dropped_subjects_to_retry),
                    sorted(subject_ids_to_drop),
                )

                # Build combined scheduled_rows from kept rows for student conflict checking
                scheduled_rows_for_retry = list(kept_rows)

                retry_results_conflict = _retry_unscheduled_subjects(
                    db,
                    dropped_subjects_to_retry,
                    course_to_instructors,
                    course_to_rooms,
                    slots_by_day,
                    booked_room_slots_retry,
                    booked_instr_slots_retry,
                    rooms,
                    days,
                    room_id_to_name,
                    course_id,
                    default_year,
                    semester,
                    focus_subject_ids_set,
                    global_instr_map=global_lec_instr_by_key,
                    scheduled_rows=scheduled_rows_for_retry,
                    booked_room_ranges_global=booked_room_ranges_global,
                    booked_instr_ranges_global=booked_instr_ranges_global,
                )

                logger.info(
                    "[POST-CONFLICT RETRY] Completed: scheduled %d/%d subjects",
                    len(retry_results_conflict),
                    len(dropped_subjects_to_retry),
                )

                # Merge retry results back in
                kept_rows.extend(retry_results_conflict.values())
        except Exception as e:
            logger.error("[POST-CONFLICT RETRY] Failed with error: %s", e)

    # Replace all_scheduled_items with kept_rows (+ any successful post-conflict retries)
    all_scheduled_items = kept_rows

    # CRITICAL: Log sample items to verify solver results are being returned correctly
    if all_scheduled_items:
        sample_items = all_scheduled_items[:3]
        for item in sample_items:
            logger.info(
                "[RETURN] Returning item: subject_id=%s, day_id=%s, time=%s, room_id=%s, instructor_id=%s",
                item.get("subject_id"),
                item.get("day_id"),
                item.get("time"),
                item.get("room_id"),
                item.get("instructor_id")
            )
        missing_fields = []
        for item in all_scheduled_items:
            if not item.get("subject_id"):
                missing_fields.append(f"subject_id missing in {item}")
            if item.get("day_id") is None:
                missing_fields.append(f"day_id missing for subject {item.get('subject_id')} in {item}")
            if not item.get("time"):
                missing_fields.append(f"time missing for subject {item.get('subject_id')} in {item}")
        if missing_fields:
            logger.error(f"[RETURN BUG] Found {len(missing_fields)} items with missing required fields! First 5: {missing_fields[:5]}")

    logger.info("\n" + "="*80)
    logger.info("DEBUG: SCHEDULE ITEMS STRUCTURE")
    logger.info("="*80)
    for i, item in enumerate(all_scheduled_items[:5]):  # Show first 5 items for debugging
        logger.info(f"\nItem {i+1}:")
        logger.info(f"  Keys: {list(item.keys())}")
        if 'subject' in item:
            logger.info(f"  Subject: {item['subject']}")
        if 'time' in item:
            logger.info(f"  Time: {item['time']}")
        if 'day_id' in item:
            logger.info(f"  Day ID: {item['day_id']}")

    formatted_schedule = format_schedule_output(all_scheduled_items, days, db=db)
    logger.info("\n" + "="*80)
    logger.info("FINAL SCHEDULE")
    logger.info("="*80)
    logger.info(formatted_schedule)
    
    # Add NSTP pre-scheduled items to the final result BEFORE calculating summary
    if nstp_scheduled_items:
        logger.info(f"Adding {len(nstp_scheduled_items)} NSTP pre-scheduled items to final result")
        all_scheduled_items.extend(nstp_scheduled_items)
    
    # CRITICAL: Log which subjects were scheduled vs unscheduled
    scheduled_subject_ids = set()
    for item in all_scheduled_items:
        sid = item.get("subject_id")
        if sid is not None:
            try:
                scheduled_subject_ids.add(int(sid))
            except (ValueError, TypeError):
                pass
    
    # Get all requested subject IDs
    all_requested_ids = set()
    if focus_subject_ids_set:
        all_requested_ids.update(focus_subject_ids_set)
    else:
        # All subjects loaded were requested
        for subject in subjects:
            all_requested_ids.add(subject.id)
    
    unscheduled_ids = all_requested_ids - scheduled_subject_ids
    if unscheduled_ids:
        logger.warning("FINAL SUMMARY: Scheduled %d/%d subjects. Unscheduled IDs: %s", 
                     len(scheduled_subject_ids), len(all_requested_ids), sorted(list(unscheduled_ids)))
        try:
            missing_subjects = db.query(models.Subject).filter(models.Subject.id.in_(sorted(list(unscheduled_ids)))).all()
        except Exception:
            missing_subjects = []
        if missing_subjects:
            for subj in missing_subjects:
                try:
                    logger.warning(
                        "UNSCHEDULED DETAIL: id=%s code=%s type=%s year=%s semester=%s",
                        getattr(subj, "id", None),
                        getattr(subj, "code", None),
                        getattr(subj, "type", None) or getattr(subj, "subject_type", None),
                        getattr(subj, "year_level", None),
                        getattr(subj, "semester", None),
                    )
                except Exception:
                    continue
    else:
        logger.info("FINAL SUMMARY: All %d requested subjects were scheduled!", len(scheduled_subject_ids))

    return all_scheduled_items




def format_schedule_output(schedule_items, days, db=None):
    """
    Format schedule items into a human-readable format.
    
    Args:
        schedule_items: List of scheduled items
        days: List of day objects with id and label
        db: Optional database session for looking up additional info
        
    Returns:
        Formatted string with schedule
    """
    from datetime import datetime
    from sqlalchemy.orm import Session
    from api.models import Subject, Room, Instructor  # Import your models
    
    if not schedule_items:
        return "No schedule items to display."
        
    # Create day mapping from ID to label
    day_map = {str(day.id): day.label for day in days}
    
    # Create caches for database lookups
    subject_cache = {}
    room_cache = {}
    instructor_cache = {}
    
    # If we have a database session, preload data we'll need
    if db and isinstance(db, Session):
        try:
            # Get all subject IDs
            subject_ids = [str(item.get('subject_id')) for item in schedule_items if item.get('subject_id')]
            if subject_ids:
                subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all()
                subject_cache = {str(subj.id): subj for subj in subjects}
                
            # Get all room IDs
            room_ids = [str(item.get('room_id')) for item in schedule_items if item.get('room_id')]
            if room_ids:
                rooms = db.query(Room).filter(Room.id.in_(room_ids)).all()
                room_cache = {str(room.id): room for room in rooms}
                
            # Get all instructor IDs
            instructor_ids = [str(item.get('instructor_id')) for item in schedule_items if item.get('instructor_id')]
            if instructor_ids:
                instructors = db.query(Instructor).filter(Instructor.id.in_(instructor_ids)).all()
                instructor_cache = {str(instr.id): instr for instr in instructors}
                
        except Exception as e:
            logger.warning(f"Error preloading data: {e}")
    
    # Group schedule items so multi-day patterns (e.g., MW, TTh) are printed
    # as a single row instead of one row per day.
    #
    # Key: (subject_id, instructor_id, room_id, course_id, year, semester, raw_time)
    day_order = {"M": 0, "T": 1, "W": 2, "TH": 3, "F": 4, "S": 5}
    grouped: Dict[Tuple[str, str, str, str, str, str, str], list] = {}
    for item in schedule_items:
        try:
            subj_id = str(item.get("subject_id", ""))
            instr_id = str(item.get("instructor_id", ""))
            room_id = str(item.get("room_id", ""))
            course_id = str(item.get("course_id", ""))
            year = str(item.get("year", ""))
            semester = str(item.get("semester", ""))
            time_raw = item.get("time", "")
            key = (subj_id, instr_id, room_id, course_id, year, semester, str(time_raw))
            grouped.setdefault(key, []).append(item)
        except Exception as e:
            logger.warning(f"Error grouping schedule item: {e}\nItem: {item}")
            continue

    formatted = []
    for key, items in grouped.items():
        # Use the first item in the group as a representative for shared fields
        item = items[0]
        try:
            # Get subject info
            subject_id = str(item.get('subject_id', ''))
            subject = subject_cache.get(subject_id, {})

            # Get subject info with fallbacks
            code = getattr(subject, 'code', None) or 'N/A'
            name = getattr(subject, 'name', None) or 'N/A'
            subj_type = getattr(subject, 'type', None) or 'N/A'
            units = getattr(subject, 'units', None) or 'N/A'

            # If we couldn't get subject info, use basic ID
            if code == 'N/A' and subject_id and subject_id != 'None':
                code = f"Subject {subject_id}"
                name = f"Subject {subject_id}"

            # Combine day labels across all items in the group
            day_labels: List[str] = []
            for it in items:
                d_id = str(it.get('day_id', ''))
                label = day_map.get(d_id)
                if label and label not in day_labels:
                    day_labels.append(label)

            # Sort days and build combined patterns like MW or TTH
            day_labels_sorted = sorted(day_labels, key=lambda d: day_order.get(d, 99))
            combined_days = ""
            if len(day_labels_sorted) == 2:
                d1, d2 = day_labels_sorted
                if {d1, d2} == {"M", "W"}:
                    combined_days = "MW"
                elif {d1, d2} == {"T", "TH"}:
                    combined_days = "TTH"
                else:
                    combined_days = "".join(day_labels_sorted)
            else:
                combined_days = "".join(day_labels_sorted)

            day_label = combined_days or (day_labels_sorted[0] if day_labels_sorted else 'N/A')

            # Format time from the representative item
            time_slot = item.get('time', '')
            time_str = "Time not specified"

            if isinstance(time_slot, str):
                # Handle case where time is a string like "9:00–10:30 - 10:30"
                time_parts = time_slot.split(' - ')
                if len(time_parts) >= 1:
                    time_range = time_parts[0]  # Get the first part "9:00–10:30"
                    time_range_parts = time_range.split('–')  # Split on en dash
                    if len(time_range_parts) == 2:
                        start, end = time_range_parts
                        time_str = f"{start.strip()} - {end.strip()}"
            elif isinstance(time_slot, dict):
                # Handle case where time is a dict with start/end
                start = time_slot.get('start', '')
                end = time_slot.get('end', '')
                if start and end:
                    time_str = f"{start} - {end}"

            # Get room info
            room_id = str(item.get('room_id', ''))
            room = room_cache.get(room_id, {})
            room_name = getattr(room, 'name', None) or f"Room {room_id}" if room_id and room_id != 'None' else 'N/A'

            # Get instructor info
            instructor_id = str(item.get('instructor_id', ''))
            instructor = instructor_cache.get(instructor_id, {})
            instructor_name = getattr(instructor, 'name', None) or f"Instructor {instructor_id}" if instructor_id and instructor_id != 'None' else 'N/A'

            # Add the formatted entry
            formatted.extend([
                f"{code}",
                f"{name}",
                f"{subj_type}",
                f"{units}",
                f"{day_label}",
                f"{time_str}",
                f"{room_name}",
                f"{instructor_name}",
                ""  # Empty line between entries
            ])

        except Exception as e:
            logger.warning(f"Error formatting schedule item: {e}\nItem: {item}")
            continue
    
    if not formatted:
        return "No valid schedule items to display. Check if the schedule was generated successfully."
    
    # Create a header row
    header = [
        "Code",
        "Name",
        "Type",
        "Units",
        "Day",
        "Time",
        "Room",
        "Instructor",
        ""  # Empty line for spacing
    ]
    
    # Combine header and formatted data
    result = [
        " | ".join(header),
        "-" * 100  # Separator line
    ]
    result.extend(formatted)
    
    return "\n".join(result)
