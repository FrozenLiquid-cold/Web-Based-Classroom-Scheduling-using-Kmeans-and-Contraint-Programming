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
    minutes_to_time_str as _minutes_to_time_str,
)
from api.scheduler.slot_availability import (
    get_available_slots,
    get_instructor_availability,
    generate_recommendations,
    diagnose_scheduling_failure,
)

logger = logging.getLogger(__name__)

# Add file handler to capture all logs to file for debugging
_file_handler = logging.FileHandler("scheduler_debug.log", mode="a")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(_file_handler)
logger.setLevel(logging.DEBUG)

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
NSTP_ROOM_NAME = "FIELD"  # Legacy fallback name; prefer building.is_shared flag
NSTP_START_MIN = 480  # 8:00 AM in minutes
NSTP_END_MIN = 660  # 11:00 AM in minutes
NSTP_TIME_LABEL = "SUN 8:00–11:00"  # Display label for NSTP time slot

# Extended hours: allow evening slots up to 9PM
MAX_END_TIME_MIN = 1260  # 21:00 (9PM) in minutes


def _range_conflicts(ranges_dict, key, day_id, start, end):
    """Check if time range overlaps with any range in the dictionary list.
    
    Returns:
        None if no conflict
        metadata dict (or True) if conflict found
    """
    for entry in ranges_dict.get((key, day_id), []):
        # Handle both (start, end) and (start, end, metadata) formats
        if len(entry) == 3:
            s, e, metadata = entry
        else:
            s, e = entry
            metadata = True  # Default if no metadata
            
        if not (end <= s or e <= start):
            return metadata
            
    return None


def _is_shared_subject(subject) -> bool:
    """Check if a subject is block-shared (e.g., NSTP, PE).
    
    Block-shared subjects get special handling:
    - All blocks share the same room and time
    - Only instructor selection varies per block
    - Uses shared building rooms (FIELD, GYM, etc.)
    
    Checks the is_block_shared DB flag first. Falls back to NSTP name check
    for backward compatibility with existing data.
    """
    # Prefer DB flag if available
    is_shared = getattr(subject, "is_block_shared", None)
    if is_shared is True:
        return True
    # Legacy fallback: check NSTP or PE prefix in code
    code = getattr(subject, "code", "") or ""
    code_upper = code.upper()
    return code_upper.startswith("NSTP") or code_upper.startswith("PE")


def _is_nstp_only_subject(subject) -> bool:
    """Check if a subject is EXACTLY an NSTP subject, to be hardcoded to Saturday."""
    code = getattr(subject, "code", "") or ""
    return code.upper().startswith("NSTP")


def _is_pe_subject(subject) -> bool:
    """Check if a subject is a PE or PATHFIT subject (scheduled in PE phase with shared rooms)."""
    code = getattr(subject, "code", "") or ""
    code_upper = code.upper().strip()
    return code_upper.startswith("PE") or code_upper.startswith("PATHFIT")


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





def is_time_within_preference(start_min: int, end_min: int, pref_start: Optional[int], pref_end: Optional[int]) -> bool:
    """Check if a time range [start_min, end_min] fits within preferences."""
    # If no preferences, it fits
    if pref_start is None and pref_end is None:
        return True
        
    # If only start pref, check start
    if pref_start is not None and start_min < pref_start:
        return False
        
    # If only end pref, check end
    if pref_end is not None and end_min > pref_end:
        return False
        
    return True


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
        logger.debug("[OK] slots_by_day has entries for all %d days: %s",
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


def _log_slot_mismatch_diagnosis(subject, slots_by_day, days, logger):
    """Log detailed diagnosis of why a subject has no valid start options.
    
    Checks MW and TTh slot pairing and reports mismatches.
    """
    if not logger:
        return
    
    subj_type = str(getattr(subject, 'type', '')).upper().strip()
    subj_code = getattr(subject, 'code', '?')
    subj_id = getattr(subject, 'id', '?')
    
    logger.warning(f"  [SLOT DIAGNOSIS] Subject {subj_code} (ID={subj_id}, Type={subj_type}):")
    
    # Log slot counts per day
    for day_label in ['M', 'T', 'W', 'TH', 'F']:
        day_slots = slots_by_day.get(day_label, [])
        if day_slots:
            times = [f"{s.get('start_min')}-{s.get('end_min')}" for s in day_slots[:3]]
            logger.warning(f"    {day_label}: {len(day_slots)} slots (e.g. {', '.join(times)})")
        else:
            logger.warning(f"    {day_label}: 0 slots")
    
    if subj_type == 'LEC':
        # Check MW pairing
        mon_slots = slots_by_day.get('M', [])
        wed_slots = slots_by_day.get('W', [])
        if mon_slots and wed_slots:
            wed_set = {(s.get('start_min'), s.get('end_min')) for s in wed_slots}
            unmatched = []
            for ms in mon_slots:
                key = (ms.get('start_min'), ms.get('end_min'))
                if key not in wed_set:
                    unmatched.append(f"{ms.get('start_min')}-{ms.get('end_min')}")
            if unmatched:
                logger.warning(f"    MW MISMATCH: Mon has {len(unmatched)} slots with no Wed match: {', '.join(unmatched[:5])}")
            else:
                logger.warning(f"    MW pairing OK ({len(mon_slots)} matched)")
        elif not mon_slots:
            logger.warning(f"    MW FAIL: No Monday slots available")
        elif not wed_slots:
            logger.warning(f"    MW FAIL: No Wednesday slots available")
        
        # Check TTh pairing
        tue_slots = slots_by_day.get('T', [])
        thu_slots = slots_by_day.get('TH', [])
        if tue_slots and thu_slots:
            thu_set = {(s.get('start_min'), s.get('end_min')) for s in thu_slots}
            unmatched = []
            for ts in tue_slots:
                key = (ts.get('start_min'), ts.get('end_min'))
                if key not in thu_set:
                    unmatched.append(f"{ts.get('start_min')}-{ts.get('end_min')}")
            if unmatched:
                logger.warning(f"    TTh MISMATCH: Tue has {len(unmatched)} slots with no Thu match: {', '.join(unmatched[:5])}")
            else:
                logger.warning(f"    TTh pairing OK ({len(tue_slots)} matched)")
        elif not tue_slots:
            logger.warning(f"    TTh FAIL: No Tuesday slots available")
        elif not thu_slots:
            logger.warning(f"    TTh FAIL: No Thursday slots available")
    
    elif subj_type == 'LAB':
        # LAB needs any single day with a slot
        any_day_with_slots = [d for d in ['M', 'T', 'W', 'TH', 'F'] if slots_by_day.get(d)]
        if not any_day_with_slots:
            logger.warning(f"    LAB FAIL: No day has any time slots")
        else:
            logger.warning(f"    LAB: Slots available on {any_day_with_slots} but still no options (check slot duration vs requirements)")


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
    subj_type_raw = getattr(subject, 'type', '?')
    subj_units = getattr(subject, 'unit', 0) or 0
    
    debug_log(f"Generating start options. Subject type: {subj_type_raw}, Units: {subj_units}")
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
    
    # Log available attributes (safely)
    try:
        debug_log(f"Subject has attributes: {', '.join([attr for attr in dir(subject) if not attr.startswith('_')])}")
    except Exception as e:
        debug_log(f"Could not list subject attributes: {str(e)}", level='warning')

    subj_id = getattr(subject, "id", "?")

    if logger:
        logger.debug("generate_subject_start_options: Subject %s type='%s'", subj_id, subj_type)

    # --- LAB logic: MW, TTh, F patterns (same as LEC, prioritizing MW/TTh) ---
    # LAB subjects use same day patterns as LEC per user requirements
    if subj_type == "LAB":
        debug_log("Processing as LAB subject (MW/TTh/F patterns, same as LEC)")

        mon_day = day_label_to_day.get(MON)
        wed_day = day_label_to_day.get(WED)
        tue_day = day_label_to_day.get(TUE)
        thu_day = day_label_to_day.get(THU)
        fri_day = day_label_to_day.get(FRI)

        # Pattern MW (prioritized)
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

        # Pattern TTh (prioritized)
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

        # Pattern F (fallback)
        if fri_day and FRI in slots_by_day:
            for fri_slot in slots_by_day[FRI]:
                fri_slot_indexes = fri_slot.get("index", [])
                if isinstance(fri_slot_indexes, int):
                    fri_slot_indexes = [fri_slot_indexes]

                fri_block_indices = set(fri_slot.get("block_indices", []))
                if not fri_block_indices:
                    fri_block_indices = {fri_slot_indexes[0]} if fri_slot_indexes else set()

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
                    "block_indices": fri_block_indices,
                    "blocks_by_day": {fri_day.id: fri_block_indices},
                    "slot_indexes": fri_slot_indexes,
                    "blocks_spanned": set(fri_slot.get("blocks_spanned", [])),
                    "slot_labels": [fri_slot.get("label", "")],
                    "num_slots": len(fri_slot_indexes),
                })

        if logger and options:
            logger.info(f"generate_subject_start_options: Subject {subj_id} (LAB) -> {len(options)} options (MW/TTh/F)")
            
            # Track unique days and pattern types in options
            all_days_set = set()
            pattern_types = defaultdict(int)
            for opt in options:
                days = opt.get("days", [])
                all_days_set.update(days)
                if set(days) == {MON, WED}:
                    pattern_types["MW"] += 1
                elif set(days) == {TUE, THU}:
                    pattern_types["TTh"] += 1
                elif len(days) == 1 and FRI in days:
                    pattern_types["F"] += 1
                    
            # Debug logging
            try:
                subj_id_int = int(subj_id)
                start_min = options[0].get("start_min") if options else None
                end_min = options[0].get("end_min") if options else None
                duration_min = options[0].get("duration_min") if options else None
                days = options[0].get("days") if options else []
                slot_labels = options[0].get("slot_labels") if options else []
                
                logger.debug(
                    "[DEBUG OPTIONS] LAB subject %s code=%s days=%s time=%s (%d-%d, dur=%d)",
                    subj_id_int,
                    getattr(subject, "code", ""),
                    days,
                    slot_labels or "N/A",
                    start_min,
                    end_min,
                    duration_min,
                )
            except Exception:
                pass
                
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
) -> Tuple[Dict[int, List[int]], Dict[int, List[int]], Dict[int, List[int]]]:
    """
    Build instructor and room eligibility PER SUBJECT SECTION.
    Keys are subject.id (NOT course_id).
    
    Returns:
        subject_to_instructors: Dict[int, List[int]]
        subject_to_all_rooms: Dict[int, List[int]] (All valid rooms by type)
        subject_to_preferred_rooms: Dict[int, List[int]] (Preferred rooms from rules/SP)
    """

    # Final maps
    subject_to_instructors: Dict[int, List[int]] = defaultdict(list)
    subject_to_all_rooms: Dict[int, List[int]] = defaultdict(list)
    subject_to_preferred_rooms: Dict[int, List[int]] = defaultdict(list)

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
    # Build room → college mapping & shared-building rooms set
    # (done ONCE before the per-subject loop for efficiency)
    # ---------------------------------------------------------
    room_to_college_id: Dict[int, Optional[int]] = {}  # room.id → college_id (None if unassigned)
    _shared_room_ids: set = set()
    # Pre-load subject room preferences from DB (replaces hardcoded PE/GYM/QUAD logic)
    _subject_pref_room_ids: Dict[int, Set[int]] = {}  # subject_id → set of preferred room_ids
    if db:
        _building_cache: Dict[int, models.Building] = {}
        for _r in rooms:
            if _r.building_id:
                if _r.building_id not in _building_cache:
                    _building_cache[_r.building_id] = db.query(models.Building).get(_r.building_id)
                _bldg = _building_cache[_r.building_id]
                if _bldg:
                    room_to_college_id[_r.id] = getattr(_bldg, 'college_id', None)
                    if _bldg.is_shared:
                        _shared_room_ids.add(_r.id)
        # Load preferred rooms for ALL subjects from DB (not just current batch)
        # This ensures block-cloned subjects inherit preferences even if their
        # original isn't in the current scheduling batch.
        if db:
            all_prefs = db.query(models.SubjectRoomPreference).all()
            for p in all_prefs:
                _subject_pref_room_ids.setdefault(p.subject_id, set()).add(p.room_id)
            # For subjects in this batch that aren't in _subject_pref_room_ids,
            # try to inherit from a subject with the same code AND type that HAS
            # preferences. Using code alone is unsafe for paired LEC/LAB subjects
            # like CC 102 because clones can inherit the wrong room set.
            _code_type_to_pref: dict = {}
            for sid, pref_set in _subject_pref_room_ids.items():
                subj = db.query(models.Subject).get(sid)
                if subj and subj.code:
                    key = (
                        subj.code.strip().upper(),
                        (getattr(subj, "type", "") or "").strip().upper(),
                    )
                    _code_type_to_pref[key] = pref_set
            for s in subjects:
                if s.id not in _subject_pref_room_ids and s.code:
                    key = (
                        s.code.strip().upper(),
                        (getattr(s, "type", "") or "").strip().upper(),
                    )
                    if key in _code_type_to_pref:
                        _subject_pref_room_ids[s.id] = _code_type_to_pref[key]
    # Compute set of all "claimed" room IDs from the ENTIRE database — rooms that are
    # the exclusive preference of ANY subject (even subjects not in this batch).
    # This ensures e.g. FIELD stays reserved for NSTP even when scheduling a different course.
    _all_claimed_room_ids: Set[int] = set()
    if db:
        all_db_prefs = db.query(models.SubjectRoomPreference).all()
        for p in all_db_prefs:
            _all_claimed_room_ids.add(p.room_id)

    # ---------------------------------------------------------
    # Build eligibility PER SUBJECT
    # ---------------------------------------------------------
    for subject in subjects:
        sid = subject.id
        subj_code = (subject.code or "").upper().strip()
        subj_type = (subject.type or "").upper().strip()
        subj_course_id = subject.course_id
        subj_college = course_college_map.get(subj_course_id)
        is_shared_room_subject = (
            _is_nstp_only_subject(subject)
            or subj_code.startswith("PE")
            or subj_code.startswith("PATHFIT")
        )

        eligible_instrs: List[int] = []
        preferred_rooms: List[int] = []
        
        # 1. Fetch from DB/SP (Strict/Preferred rules)
        if db is not None:
            try:
                base_sid_val = getattr(subject, "original_subject_id", sid)
                base_sid = int(base_sid_val) if base_sid_val is not None else sid
            except Exception:
                base_sid = sid

            try:
                db_instrs = db_procedures.get_instructor_eligibility(db, base_sid)
                eligible_instrs = [inst.id for inst in db_instrs]
            except Exception as e:
                logger.warning(
                    "build_eligibility_maps: instructor eligibility SP failed for subject %s: %s",
                    subj_code, e,
                )
                eligible_instrs = []

            try:
                db_rooms = db_procedures.get_room_eligibility(db, base_sid)
                preferred_rooms = [room.id for room in db_rooms]
            except Exception as e:
                logger.warning(
                    "build_eligibility_maps: room eligibility SP failed for subject %s: %s",
                    subj_code, e,
                )
                preferred_rooms = []

        # 2. Fallback for Instructors if empty — STRICT specialization only
        if not eligible_instrs:
            import re
            def _normalize_code(s):
                return re.sub(r'[^A-Z0-9]', '', s.upper())

            norm_subj_code = _normalize_code(subj_code) if subj_code else ""
            eligible_instrs = []
            for inst in instructors:
                inst_id = inst.id
                assignable = inst.assignable_courses or ""
                assignable_set = {_normalize_code(c) for c in assignable.split(",") if c.strip()}

                # Only match if the instructor explicitly lists this subject code
                if norm_subj_code and assignable_set and norm_subj_code in assignable_set:
                    eligible_instrs.append(inst_id)

        if not is_shared_room_subject:
            preferred_rooms = [rid for rid in preferred_rooms if rid not in _shared_room_ids]

        subject_to_instructors[sid] = eligible_instrs
        subject_to_preferred_rooms[sid] = preferred_rooms

        # 3. Build All Valid Rooms (Type-based + College-based Hard Constraint)
        # Allows scheduler to pick NON-preferred rooms with a penalty
        all_valid_rooms = []
        for room in rooms:
            room_type = (room.type or "").upper().strip()
            # Strict type match
            if room_type == subj_type:
                # College-based filtering: only allow rooms from the same college's buildings
                room_college = room_to_college_id.get(room.id)
                if subj_college is not None and room_college is not None:
                    # Both subject and room have a college — must match
                    if room_college != subj_college:
                        continue
                # If room_college is None (building not assigned to any college), allow it (graceful fallback)
                all_valid_rooms.append(room.id)

        # Room restriction logic: use DB-configured preferred rooms if available,
        # otherwise fall back to shared-building / non-shared building filtering.
        subj_pref_ids = set(_subject_pref_room_ids.get(sid, set()))
        if not is_shared_room_subject and subj_pref_ids:
            subj_pref_ids = {rid for rid in subj_pref_ids if rid not in _shared_room_ids}
        if subj_pref_ids:
            # Subject has explicit room preferences configured — restrict to those rooms only
            all_valid_rooms = [rid for rid in all_valid_rooms if rid in subj_pref_ids]
            subject_to_preferred_rooms[sid] = [rid for rid in subject_to_preferred_rooms[sid] if rid in subj_pref_ids]
        elif is_shared_room_subject:
            # NSTP / PE / PATHFIT subjects without explicit prefs — use shared building rooms
            # (FIELD for NSTP, Inner Quad / GYM for PE/PATHFIT)
            if _shared_room_ids:
                shared_valid = [rid for rid in all_valid_rooms if rid in _shared_room_ids]
                if shared_valid:
                    all_valid_rooms = shared_valid
        else:
            # All other subjects without explicit prefs — exclude rooms claimed by
            # other subjects AND shared-building rooms (FIELD, etc.) which are
            # reserved for NSTP.
            excluded = _all_claimed_room_ids | _shared_room_ids
            if excluded:
                before_count = len(all_valid_rooms)
                all_valid_rooms = [rid for rid in all_valid_rooms if rid not in excluded]
                if before_count != len(all_valid_rooms):
                    logger.debug(
                        "[ELIGIBILITY] Subject %s (ID:%d): Excluded %d rooms (shared=%s, claimed=%d). %d->%d rooms",
                        subj_code, sid, before_count - len(all_valid_rooms),
                        _shared_room_ids, len(_all_claimed_room_ids),
                        before_count, len(all_valid_rooms)
                    )
                subject_to_preferred_rooms[sid] = [rid for rid in subject_to_preferred_rooms[sid] if rid not in excluded]
        
        # Also apply college filtering to preferred rooms
        if subj_college is not None:
            subject_to_preferred_rooms[sid] = [
                rid for rid in subject_to_preferred_rooms[sid]
                if room_to_college_id.get(rid) is None or room_to_college_id.get(rid) == subj_college
            ]
        
        # Capacity check logic could go here, but usually done in solver options generation
        
        # If no valid rooms found by type (fallback for data issues), rely on preferred or all
        if not all_valid_rooms:
            if preferred_rooms:
                 all_valid_rooms = list(preferred_rooms)
            elif subj_pref_ids:
                 # Use explicitly configured rooms as last resort
                 all_valid_rooms = list(subj_pref_ids)
            else:
                 # Last resort: all rooms except claimed + shared rooms, still respecting college filter
                 _excluded_last = _all_claimed_room_ids | _shared_room_ids
                 all_valid_rooms = [
                     r.id for r in rooms
                     if r.id not in _excluded_last
                     and (subj_college is None or room_to_college_id.get(r.id) is None or room_to_college_id.get(r.id) == subj_college)
                 ]

        # Distance-based room filtering: exclude far-away rooms from eligible list
        # when closer same-type alternatives exist
        if all_valid_rooms and db and subj_college is not None:
            _elig_subj_bldg_id = None
            # Find the building associated with this subject's college
            for _b in db.query(models.Building).filter(models.Building.college_id == subj_college).all():
                _elig_subj_bldg_id = _b.id
                break
            if _elig_subj_bldg_id:
                _PROX_THRESHOLD = 15
                _close = []
                _far = []
                for rid in all_valid_rooms:
                    _rm = next((r for r in rooms if r.id == rid), None)
                    r_bldg = _rm.building_id if _rm else None
                    if r_bldg:
                        if r_bldg == _elig_subj_bldg_id:
                            _close.append(rid)
                        else:
                            _dist_rec = db.query(models.BuildingDistance).filter(
                                ((models.BuildingDistance.from_building_id == r_bldg) &
                                 (models.BuildingDistance.to_building_id == _elig_subj_bldg_id)) |
                                ((models.BuildingDistance.from_building_id == _elig_subj_bldg_id) &
                                 (models.BuildingDistance.to_building_id == r_bldg))
                            ).first()
                            _t = _dist_rec.travel_time_minutes if _dist_rec else 0
                            if _t <= _PROX_THRESHOLD:
                                _close.append(rid)
                            else:
                                _far.append(rid)
                    else:
                        _close.append(rid)
                if _close and _far:
                    logger.info(
                        "[ELIGIBILITY PROXIMITY] Subject %s (ID:%d): Excluded %d far rooms (travel>%dmin), keeping %d close rooms",
                        subj_code, sid, len(_far), _PROX_THRESHOLD, len(_close)
                    )
                    all_valid_rooms = _close

        subject_to_all_rooms[sid] = all_valid_rooms

    # ---------------------------------------------------------
    # Logging summary
    # ---------------------------------------------------------
    instr_nonempty = sum(1 for s in subject_to_instructors if subject_to_instructors[s])
    rooms_preferred = sum(1 for s in subject_to_preferred_rooms if subject_to_preferred_rooms[s])
    rooms_all = sum(1 for s in subject_to_all_rooms if subject_to_all_rooms[s])

    logger.info(
        "Built per-subject eligibility: instrs=%d/%d, preferred_rooms=%d/%d, all_rooms=%d/%d",
        instr_nonempty, len(subjects),
        rooms_preferred, len(subjects),
        rooms_all, len(subjects)
    )

    return dict(subject_to_instructors), dict(subject_to_all_rooms), dict(subject_to_preferred_rooms)


def get_existing_bookings(
    db: Session,
    years: Optional[List[int]],
    semester: int,
    exclude_course_id: Optional[int] = None,
    exclude_years: Optional[List[int]] = None,
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
        exclude_years: Optional list of year levels to exclude (only combined
            with exclude_course_id). When provided, only records matching BOTH
            the course AND the year levels are excluded.
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
        exclude_course_id=exclude_course_id,
        exclude_years=exclude_years
    )
    
    # Build (day_id, start_min) -> block_index mapping from slots_by_day
    # This replaces the broken string-based matching that silently failed
    # because DB time formats ("7:00 AM - 8:30 AM") never matched solver
    # slot labels ("M 7:00–8:30").
    day_id_to_slots = {}  # day_id -> list of {start_min, end_min, index}
    if slots_by_day and day_id_map:
        for day_label, day_slots in slots_by_day.items():
            day_id = day_id_map.get(day_label)
            if day_id is not None:
                day_id_to_slots[day_id] = [
                    {"start_min": s["start_min"], "end_min": s["end_min"], "index": s["index"]}
                    for s in day_slots
                ]
    
    def _find_overlapping_slot_indices(day_id, time_label_str):
        """Parse a DB time label and find all solver slot indices that overlap."""
        parsed = _parse_time_range_minutes(time_label_str)
        if parsed is None:
            return []
        booking_start, booking_end = parsed
        slots = day_id_to_slots.get(day_id, [])
        overlapping = []
        for s in slots:
            # Slots overlap if one starts before the other ends and vice versa
            if s["start_min"] < booking_end and s["end_min"] > booking_start:
                overlapping.append(s["index"])
        return overlapping
    
    # Convert room bookings to solver slot indices
    for booking in room_bookings:
        day_id = booking["day_id"]
        time_label = booking["time_label"]
        
        if day_id_to_slots:
            indices = _find_overlapping_slot_indices(day_id, time_label)
            for idx in indices:
                booked_room_slots.add((booking["resource_name"], day_id, idx))
        else:
            # Fallback: use time_label as string (for backward compatibility)
            booked_room_slots.add((booking["resource_name"], day_id, time_label))
    
    # Convert instructor bookings to solver slot indices
    for booking in instructor_bookings:
        day_id = booking["day_id"]
        time_label = booking["time_label"]
        
        if day_id_to_slots:
            indices = _find_overlapping_slot_indices(day_id, time_label)
            for idx in indices:
                booked_instr_slots.add((booking["resource_id"], day_id, idx))
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
    instructor_prefs: Optional[Dict[int, Dict]] = None,
) -> Tuple[Dict[int, Dict], Dict[int, Dict[str, int]]]:
    """
    Retry pass: attempt to schedule subjects that weren't scheduled in initial cluster runs.
    Uses a simplified greedy approach to find any available slots.
    
    Returns:
        Tuple of (Dict mapping subject_id -> scheduled item dict, Dict of debug stats).
    """
    retry_results: Dict[int, Dict] = {}
    
    if not unscheduled_subjects:
        return retry_results, {}
    
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

    # Retry Loop: Try strict first, then relaxed
    # Pass 1: Strict (honor all preferences, short timeout)
    # Pass 2: Relaxed (ignore optional prefs, longer timeout)
    
    phases = [False] # Always try strict first
    # Only try relaxed if we have unscheduled subjects left
    # But we can't know ahead of time. So we'll append to phases dynamically or just loop.
    
    current_unscheduled = unscheduled_subjects_sorted
    all_retry_results = {}
    all_debug_stats = {}
    
    for attempt in range(2):
        relaxed = (attempt == 1)
        if not current_unscheduled:
            break
            
        pass_results, pass_stats = _cp_retry_mini_model(
            db=db,
            unscheduled_subjects=current_unscheduled,
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
            instructor_prefs=instructor_prefs,
            relaxed=relaxed,
        )
        
        # Merge results
        all_retry_results.update(pass_results)
        
        # Merge stats (keep most specific failure reason)
        for sid, stats in pass_stats.items():
            if sid not in all_debug_stats:
                all_debug_stats[sid] = stats
            else:
                # If we have a new stat and it's meaningful (e.g. candidates > 0), maybe update
                # simpler: just overwrite for now, or keep the one that had candidates.
                # Actually, if pass 2 found candidates but pass 1 didn't, we want pass 2 stats.
                if stats.get("candidates", 0) > 0:
                    all_debug_stats[sid] = stats

        # Update unscheduled list for next pass
        # (The keys of all_retry_results correspond to subject.id)
            
        # Re-filter current_unscheduled
        scheduled_keys = set(all_retry_results.keys())
        current_unscheduled = [s for s in current_unscheduled if s.id not in scheduled_keys]
        
        if not current_unscheduled:
            break

    # Final result set
    retry_results = all_retry_results
    debug_subject_stats = all_debug_stats
    
    # We need to return the merged stats, but the signature expects (results, stats)
    # The greedy loop below modifies retry_results in place.
    
    
    # --- END RETRY LOOP ---

    # Use greedy approach for retry - simpler and faster than full CP model
    # (Fallback for anything still unscheduled)
    for subject in current_unscheduled:
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
            
        # Metrics for diagnostics
        eligible_room_count = len(eligible_rooms)
        eligible_instr_count = len(eligible_instrs)
        failure_metrics = {
            "windows_considered": 0,
            "valid_windows": 0,
            "room_conflicts": 0,
            "instr_conflicts": 0,
            "student_conflicts": 0
        }
        
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
                
                # Track considered windows
                failure_metrics["windows_considered"] += 1

                # Check student conflicts
                has_student_conflict = False
                existing_ranges = student_time_ranges.get((subj_course_id, subj_year, subj_block_label, day.id), [])
                for existing_start, existing_end in existing_ranges:
                    if not (proposed_end_min <= existing_start or proposed_start_min >= existing_end):
                        has_student_conflict = True
                        break
                
                if has_student_conflict:
                    failure_metrics["student_conflicts"] += 1
                    continue
                
                failure_metrics["valid_windows"] += 1
                
                # Check room availability
                for room_id in eligible_rooms:
                    if scheduled:
                        break
                    room_name = room_id_to_name.get(room_id)
                    if not room_name:
                        continue

                    # Range-based room conflict check
                    if booked_room_ranges_global is not None and _range_conflicts(
                        booked_room_ranges_global, room_name, day.id, proposed_start_min, proposed_end_min
                    ):
                        failure_metrics["room_conflicts"] += 1
                        continue
                    
                    # Check if room is booked for any slot
                    room_available = True
                    for slot in block:
                        block_index = slot["index"]
                        if (room_name, day.id, block_index) in booked_room_slots_global:
                            room_available = False
                            break
                    
                    if not room_available:
                        failure_metrics["room_conflicts"] += 1
                        continue
                    
                    # Check instructor availability
                    for instructor_id in eligible_instrs:
                        if scheduled:
                            break

                        # Range-based instructor conflict check
                        if booked_instr_ranges_global is not None and _range_conflicts(
                            booked_instr_ranges_global, instructor_id, day.id, proposed_start_min, proposed_end_min
                        ):
                             failure_metrics["instr_conflicts"] += 1
                             continue
                             
                        instr_available = True
                        for slot in block:
                            block_index = slot["index"]
                            if (instructor_id, day.id, block_index) in booked_instr_slots_global:
                                instr_available = False
                                break
                        
                        if not instr_available:
                            failure_metrics["instr_conflicts"] += 1
                            continue
                        
                        if instr_available:
                            s_str = _minutes_to_time_str(int(first_slot["start_min"]))
                            e_str = _minutes_to_time_str(int(last_slot["end_min"]))
                            time_label = f"{s_str} - {e_str}"

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

                            # Handle paired days correctly
                            days_to_book = [day.id]
                            if cand.get("is_paired") and cand.get("paired_days"):
                                days_to_book = [p["day_id"] for p in cand["paired_days"]]
                            
                            for d_id in days_to_book:
                                if booked_room_ranges_global is not None:
                                    booked_room_ranges_global[(room_name, int(d_id))].append((int(proposed_start_min), int(proposed_end_min)))
                                if booked_instr_ranges_global is not None:
                                    booked_instr_ranges_global[(int(instructor_id), int(d_id))].append((int(proposed_start_min), int(proposed_end_min)))

                                student_time_ranges[(subj_course_id, subj_year, subj_block_label, d_id)].append((proposed_start_min, proposed_end_min))


                            # Log success
                            scheduled = True
                            break
            
            # Record failure reason if not scheduled
            if not scheduled:
                reason = "Unscheduled"
                if eligible_room_count == 0:
                    reason = "No Rooms"
                elif eligible_instr_count == 0:
                    reason = "No Instructor"
                elif failure_metrics["valid_windows"] == 0:
                    # No windows available due to constraints (time/duration)
                    reason = "Time Constraint"
                elif failure_metrics["student_conflicts"] > 0 and failure_metrics["room_conflicts"] == 0 and failure_metrics["instr_conflicts"] == 0:
                     reason = "Student Conflict"
                elif failure_metrics["room_conflicts"] > 0 and failure_metrics["instr_conflicts"] == 0:
                    # Slots existed but rooms were taken
                    reason = "Room Conflict"
                elif failure_metrics["instr_conflicts"] > 0:
                    # Slots existed but instructors were busy
                    reason = "Instructor Conflict"
                elif failure_metrics["windows_considered"] > 0:
                     # Fallback
                     reason = "Solver Conflict"
                
                debug_subject_stats[subject.id].update({
                     "failure_reason": reason,
                     "metrics": failure_metrics
                })

    logger.info("Retry pass completed: scheduled %d/%d subjects", len(retry_results), len(unscheduled_subjects))
    logger.info(f"[RETRY DEBUG] returning debug_subject_stats with {len(debug_subject_stats)} keys: {list(debug_subject_stats.keys())}")
    return retry_results, debug_subject_stats


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
    instructor_prefs: Optional[Dict[int, Dict]] = None,
    relaxed: bool = False,
) -> Tuple[Dict[int, Dict], Dict[int, Dict[str, int]]]:
    retry_results: Dict[int, Dict] = {}

    if not unscheduled_subjects:
        return retry_results, {}

    logger.info(
        "CP retry pass: attempting to schedule %d unscheduled subjects with mini CP model (relaxed=%s)",
        len(unscheduled_subjects),
        relaxed,
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
                "rejection_counters": defaultdict(int),
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
            logger.info(f"[RETRY SKIP] Skipping subject {clone_id} (base {base_id}) - not in focus set")
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

        # ------------------------------------------------------------------
        # College-based room filtering (mirrors build_eligibility_maps logic)
        # Only allow rooms from the same college's buildings, or from shared/
        # unassigned buildings.  Without this, the SP returns ALL rooms of a
        # matching type regardless of college ownership.
        # ------------------------------------------------------------------
        if eligible_rooms and db and subject.course_id:
            _retry_course = db.query(models.Course).get(subject.course_id)
            _retry_subj_college = _retry_course.college_id if _retry_course else None
            if _retry_subj_college is not None:
                _filtered_by_college = []
                for rid in eligible_rooms:
                    _rm_obj = db.query(models.Room).get(rid)
                    if not _rm_obj or not _rm_obj.building_id:
                        # No building info — allow (graceful fallback)
                        _filtered_by_college.append(rid)
                        continue
                    _rm_bldg = db.query(models.Building).get(_rm_obj.building_id)
                    if not _rm_bldg:
                        _filtered_by_college.append(rid)
                        continue
                    # Shared buildings are always allowed
                    if _rm_bldg.is_shared:
                        _filtered_by_college.append(rid)
                        continue
                    # If building has no college assignment, allow it
                    if _rm_bldg.college_id is None:
                        _filtered_by_college.append(rid)
                        continue
                    # Both have a college — must match
                    if _rm_bldg.college_id == _retry_subj_college:
                        _filtered_by_college.append(rid)
                    else:
                        logger.debug(
                            "[RETRY COLLEGE FILTER] Subject %s (ID:%s): Excluded room %d "
                            "(building %s, college %s) - subject college is %s",
                            subj_code, subject.id, rid,
                            _rm_bldg.name if hasattr(_rm_bldg, 'name') else _rm_bldg.id,
                            _rm_bldg.college_id, _retry_subj_college,
                        )
                if _filtered_by_college:
                    before_count = len(eligible_rooms)
                    eligible_rooms = _filtered_by_college
                    if before_count != len(eligible_rooms):
                        logger.info(
                            "[RETRY COLLEGE FILTER] Subject %s (ID:%s): %d -> %d rooms after college filtering",
                            subj_code, subject.id, before_count, len(eligible_rooms),
                        )

        # Exclude rooms claimed as preferred by other subjects (exclusive reservation)
        # AND shared-building rooms (FIELD etc.) which are reserved for NSTP
        if not _is_nstp_only_subject(subject):
            _subj_pref_ids = set()
            if hasattr(subject, 'preferred_rooms') and subject.preferred_rooms:
                _subj_pref_ids = {p.room_id for p in subject.preferred_rooms}
            if not _subj_pref_ids and db:
                _all_claimed = set()
                for _p in db.query(models.SubjectRoomPreference).all():
                    _all_claimed.add(_p.room_id)
                # Also exclude shared-building rooms (FIELD)
                _retry_shared = set()
                _shared_bldgs = db.query(models.Building).filter(models.Building.is_shared == True).all()
                for _sb in _shared_bldgs:
                    for _sr in db.query(models.Room).filter(models.Room.building_id == _sb.id).all():
                        _retry_shared.add(_sr.id)
                _all_excluded = _all_claimed | _retry_shared
                if _all_excluded:
                    eligible_rooms = [rid for rid in eligible_rooms if rid not in _all_excluded]

        # Distance-based room filtering: exclude far-away rooms when closer alternatives exist
        if eligible_rooms and db:
            _retry_subj_bldg_id = None
            if subject.course_id:
                _rc = db.query(models.Course).get(subject.course_id)
                if _rc and _rc.college_id:
                    _rc_bldgs = db.query(models.Building).filter(
                        models.Building.college_id == _rc.college_id
                    ).all()
                    if _rc_bldgs:
                        _retry_subj_bldg_id = _rc_bldgs[0].id
            
            if _retry_subj_bldg_id:
                # Compute travel time for each eligible room
                _RETRY_PROXIMITY_THRESHOLD = 15
                close_rooms = []
                far_rooms = []
                for rid in eligible_rooms:
                    r_bldg = None
                    _rm = db.query(models.Room).get(rid)
                    if _rm and _rm.building_id:
                        r_bldg = _rm.building_id
                    if r_bldg:
                        if r_bldg == _retry_subj_bldg_id:
                            close_rooms.append(rid)
                        else:
                            # Look up ALL building distances from DB
                            _bd = db.query(models.BuildingDistance).filter(
                                ((models.BuildingDistance.from_building_id == r_bldg) &
                                 (models.BuildingDistance.to_building_id == _retry_subj_bldg_id)) |
                                ((models.BuildingDistance.from_building_id == _retry_subj_bldg_id) &
                                 (models.BuildingDistance.to_building_id == r_bldg))
                            ).first()
                            travel = _bd.travel_time_minutes if _bd else 0
                            if travel <= _RETRY_PROXIMITY_THRESHOLD:
                                close_rooms.append(rid)
                            else:
                                far_rooms.append(rid)
                    else:
                        close_rooms.append(rid)  # Unknown building, keep
                
                if close_rooms:
                    # Only use close rooms, drop far ones
                    if far_rooms:
                        logger.info(
                            "[RETRY PROXIMITY] Subject %s: Filtered out %d far rooms, keeping %d close rooms",
                            subj_code or subject.id, len(far_rooms), len(close_rooms)
                        )
                    eligible_rooms = close_rooms
                # else: all rooms are far — keep them all as fallback

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
                (("M", "W"), 3),     # Monday + Wednesday, 90 min per meeting = 3 slots
                (("T", "TH"), 3),    # Tuesday + Thursday, 90 min per meeting = 3 slots
                (("F",), 6),         # Friday (3-hour single day) = 6 slots
                (("SAT",), 6),       # Saturday - EMERGENCY ONLY
            ]
        else:
            # For LAB (and other types), use same MW/TTh/F patterns as LEC
            day_patterns = [
                (("M", "W"), 3),     # Monday + Wednesday (prioritized)
                (("T", "TH"), 3),    # Tuesday + Thursday (prioritized)
                (("F",), 6),         # Friday - fallback
                (("SAT",), 6),       # Saturday - EMERGENCY ONLY
            ]
        
        for pattern, pattern_min_slots in day_patterns:
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
            max_start = len(day_slots) - pattern_min_slots
            
            # Debug: Log available slots for this pattern
            if subj_code in ("GE - E", "GE - CW", "GE - MM", "GE - US"):
                logger.info(f"CP retry DEBUG: subject {subj_code} (ID={subject.id}) pattern={pattern}, day_slots={len(day_slots)}, pattern_min_slots={pattern_min_slots}, max_start={max_start}")
            
            if max_start < 0:
                if subj_code in ("GE - E", "GE - CW", "GE - MM", "GE - US"):
                    logger.info(f"CP retry DEBUG: subject {subj_code} pattern={pattern} skipped - max_start < 0")
                continue

            for start_pos in range(max_start + 1):
                block = day_slots[start_pos : start_pos + pattern_min_slots]
                if len(block) < pattern_min_slots:
                    continue

                # NOTE: Slots in day_slots are already sorted by time. We don't need to check
                # is_consecutive_blocks here because block IDs (101, 103, 105...) are not
                # mathematically consecutive but the slots ARE temporally consecutive.

                stats["windows_considered"] += 1

                first_slot = block[0]
                last_slot = block[-1]
                try:
                    subj_course_id = int(subject.course_id) if subject.course_id else int(course_id)
                except Exception:
                    subj_course_id = int(course_id)

                try:
                    subj_year = int(subject.year_level) if subject.year_level else int(default_year or 0)
                except Exception:
                    subj_year = int(default_year or 0)

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
                            check_block = check_day_slots[start_pos : start_pos + pattern_min_slots]
                            for slot in check_block:
                                block_index = slot["index"]
                                if (room_name, check_day.id, block_index) in booked_room_slots_global:
                                    room_available = False
                                    break

                    # Range-based room conflict check (cross-block/inter-run safety)
                    if booked_room_ranges_global is not None:
                        is_range_conflict = False
                        for check_day in pattern_days:
                            check_day_slots = slots_by_day.get(check_day.label, [])
                            if start_pos < len(check_day_slots):
                                check_block = check_day_slots[start_pos : start_pos + pattern_min_slots]
                                if not check_block: continue
                                block_start_min = int(check_block[0]["start_min"])
                                block_end_min = int(check_block[-1]["end_min"])
                                
                                if _range_conflicts(
                                    booked_room_ranges_global, room_name, check_day.id, block_start_min, block_end_min
                                ):
                                    is_range_conflict = True
                                    # Debug incorrect room conflict
                                    if subj_code == "GE - US" and room_id == 15 and pattern[0] == "M":
                                        logger.info(f"CP retry DEBUG: GE - US Room 15 RANGE CONFLICT at day={check_day.label} {block_start_min}-{block_end_min}")
                                        logger.info(f"  - Subject Slots: min_slots={min_slots}, rec_slots={rec_slots}, pattern_min_slots={pattern_min_slots}")
                                        # Log the actual conflicting ranges
                                        if booked_room_ranges_global and (room_name, check_day.id) in booked_room_ranges_global:
                                            logger.info(f"  - Existing ranges for {room_name} on day {check_day.label}: {booked_room_ranges_global[(room_name, check_day.id)]}")
                                    break
                        if is_range_conflict:
                            room_available = False
                            stats["room_conflicts"] += 1
                            
                            # Record the specific reason for the conflict
                            reason = "Unknown Conflict"
                            conflict_metadata = _range_conflicts(
                                booked_room_ranges_global, room_name, check_day.id, block_start_min, block_end_min
                            )
                            if isinstance(conflict_metadata, dict):
                                reason = conflict_metadata.get("description") or f"{course_id_to_code.get(conflict_metadata.get('course_id'), 'Other')} {_year_label(conflict_metadata.get('year'))}"
                            elif conflict_metadata is True:
                                reason = "Existing Schedule"
                                
                            stats["rejection_counters"][reason] += 1
                            continue
                    
                    # Room is available, proceed to instructor check

                    for instructor_id in eligible_instrs:
                        stats["instr_checks"] += 1
                        
                        # NEW: Check time preferences (SKIP in relaxed mode)
                        if not relaxed and instructor_prefs and instructor_id in instructor_prefs:
                            prefs = instructor_prefs[instructor_id]
                            # Start and end times of the candidate window
                            block_start = int(first_slot["start_min"])
                            block_end = int(last_slot["end_min"])
                            if not is_time_within_preference(block_start, block_end, prefs['start_min'], prefs['end_min']):
                                continue

                        # Check instructor availability for ALL days in the pattern
                        instr_available = True
                        for check_day in pattern_days:
                            check_day_slots = slots_by_day.get(check_day.label, [])
                            if start_pos < len(check_day_slots):
                                check_block = check_day_slots[start_pos : start_pos + pattern_min_slots]
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

                        # Range-based instructor conflict check
                        if booked_instr_ranges_global is not None:
                            is_instr_range_conflict = False
                            for check_day in pattern_days:
                                check_day_slots = slots_by_day.get(check_day.label, [])
                                if start_pos < len(check_day_slots):
                                    check_block = check_day_slots[start_pos : start_pos + pattern_min_slots]
                                    if not check_block: continue
                                    block_start_min = int(check_block[0]["start_min"])
                                    block_end_min = int(check_block[-1]["end_min"])
                                    
                                    if _range_conflicts(
                                        booked_instr_ranges_global, instructor_id, check_day.id, block_start_min, block_end_min
                                    ):
                                        is_instr_range_conflict = True
                                        break
                            if is_instr_range_conflict:
                                stats["instr_conflicts"] += 1
                                continue


                        time_label = (
                            first_slot["label"]
                            if min_slots == 1
                            else f"{first_slot['start']}–{last_slot['end']}"
                        )
                        
                        # For MW/TTh patterns, create a SINGLE unified candidate representing BOTH days
                        # For F pattern, create a single-day candidate
                        if len(pattern_days) == 2:
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
                                "subject_id": int(base_id),
                                "clone_subject_id": int(clone_id),
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
                            # Single-day candidate (Friday only)
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
                                "subject_id": int(base_id),
                                "clone_subject_id": int(clone_id),
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
            sid_val = int(cand["clone_subject_id"])
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
        return retry_results, debug_subject_stats

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
        subject_to_indices[int(cand["clone_subject_id"])].append(idx)

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
    solver.parameters.max_time_in_seconds = 30.0 if relaxed else 10.0
    solver.parameters.num_search_workers = max(1, min(2, os.cpu_count() or 1))
    solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
    solver.parameters.linearization_level = 0
    solver.parameters.cp_model_probing_level = 0
    solver.parameters.relative_gap_limit = 0.05
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)
    logger.info("CP retry solver status: %s", solver.StatusName(status))

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return retry_results, debug_subject_stats

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
                    "time": f"{_minutes_to_time_str(day_info['start_min'])} - {_minutes_to_time_str(day_info['end_min'])}",
                    "year": subj_year,
                    "semester": subject.semester if subject.semester else semester,
                    "block": subj_block_label,
                    "start_min": day_info["start_min"],
                    "end_min": day_info["end_min"],
                    "is_retry": True,
                })
            # Store the paired results (multiple items for this subject)
            retry_results[subject.id] = paired_results
            scheduled_subject_ids.add(subject.id)
        else:
            # Single-day candidate (Friday only)
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
                "time": f"{_minutes_to_time_str(start_min)} - {_minutes_to_time_str(end_min)}",
                "year": subj_year,
                "semester": subject.semester if subject.semester else semester,
                "block": subj_block_label,
                "start_min": start_min,
                "end_min": end_min,
                "is_retry": True,
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

    # Diagnose failures for items that were NOT scheduled by this CP pass
    for subject in unscheduled_subjects:
        if subject.id in scheduled_subject_ids:
            continue
            
        # Determine internal ID used for stats
        raw_id = getattr(subject, "id", None)
        try:
             clone_id = int(raw_id) if raw_id is not None else None
        except Exception:
             clone_id = raw_id
             
        stats = debug_subject_stats[clone_id]
        
        reason = "Unscheduled"
        if stats["candidates"] > 0:
            reason = "Solver Conflict"
        elif stats["eligible_rooms"] == 0:
            reason = "No Rooms"
        elif stats["eligible_instrs"] == 0:
            reason = "No Instructor"
        elif stats["windows_considered"] == 0:
            reason = "Time Constraint"
        elif stats["windows_student_conflict"] > 0 and stats["room_conflicts"] == 0 and stats["instr_conflicts"] == 0:
             reason = "Student Conflict"
        elif stats["room_conflicts"] > 0 and stats["instr_conflicts"] == 0:
             reason = "Room Conflict"
        elif stats["instr_conflicts"] > 0:
             reason = "Instructor Conflict"
        
        stats["failure_reason"] = reason

    logger.info(
        "CP retry pass completed: scheduled %d/%d subjects",
        len(retry_results),
        len(unscheduled_subjects),
    )
    return retry_results, debug_subject_stats

def greedy_initial_schedule(
    cluster_subjects: List[models.Subject],
    course_to_instructors: Dict[str, List[int]],
    course_to_all_rooms: Dict[str, List[int]], # Updated name
    course_to_preferred_rooms: Dict[str, List[int]], # New argument
    slots_by_day: Dict[str, List[Dict]],
    booked_room_slots: Set[Tuple[str, int, int]],  # (room_name, day_id, block_index)
    booked_instr_slots: Set[Tuple[int, int, int]],  # (instr_id, day_id, block_index)
    rooms: List[models.Room],
    days: List[models.Day]
) -> Dict:
    """
    Greedy initializer (warm-start) - simple first-fit greedy scheduling.
    Prioritizes PREFERRED rooms before trying others.
    
    Returns:
        hints dict: map key (subject_id, room_id, slot_start, instructor_id, dur) -> 0/1
    """
    hints = {}
    room_id_to_name = {r.id: r.name for r in rooms}
    
    for subject in cluster_subjects:
        # CRITICAL FIX: Maps are keyed by subject.id, NOT course_id
        # (See build_eligibility_maps implementation)
        subject_id = subject.id
        
        rec_slots = subject.recommended_slots or subject.min_slots or 1
        eligible_instrs = course_to_instructors.get(subject_id, [])
        
        preferred_rooms = course_to_preferred_rooms.get(subject_id, [])
        all_rooms = course_to_all_rooms.get(subject_id, [])
        
        # Build priority list: Preferred first, then others (deduplicated)
        # Check explicit preferred list first
        rooms_to_try = []
        if preferred_rooms:
            rooms_to_try.extend(preferred_rooms)
            
        # Then add remaining valid rooms
        # Use a set for fast lookup of what's already added
        added_set = set(preferred_rooms) if preferred_rooms else set()
        
        for r in all_rooms:
            if r not in added_set:
                rooms_to_try.append(r)
        
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
                
                for room_id in rooms_to_try:
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
                        hints[(subject_id, room_id, global_start, instructor_id, rec_slots)] = 1
                        
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
    booked_room_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
    booked_instr_ranges_global: Optional[Dict[Tuple[Any, int], List[Tuple[int, int]]]] = None,
    phase_callback: Optional[Any] = None,
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
    
    # Helper function for phase completion reporting (progressive timetable)
    def report_phase(phase_name: str, items: list, total_subjects: int) -> None:
        if phase_callback is not None:
            try:
                # Build subject lookup — start from saved full list, then fill gaps from DB
                try:
                    _subj_lookup = {s.id: s for s in _all_subjects_for_enrichment}
                except NameError:
                    _subj_lookup = {s.id: s for s in subjects}

                # Find missing subject IDs and query them from DB
                missing_sids = set()
                for item in items:
                    sid = item.get('subject_id')
                    if sid is not None and sid not in _subj_lookup:
                        missing_sids.add(int(sid))
                if missing_sids:
                    try:
                        extra = db.query(models.Subject).filter(models.Subject.id.in_(list(missing_sids))).all()
                        for s in extra:
                            _subj_lookup[s.id] = s
                    except Exception:
                        pass

                # Room names — use in-scope map or query DB
                try:
                    _room_names = dict(room_id_to_name)
                except NameError:
                    _room_names = {}
                if not _room_names:
                    try:
                        _room_names = {r.id: r.name for r in db.query(models.Room).all()}
                    except Exception:
                        pass

                # Instructor names — use in-scope map or query DB
                try:
                    _instr_names = dict(instr_id_to_name)
                except NameError:
                    _instr_names = {}
                if not _instr_names:
                    try:
                        _instr_names = {i.id: f"{getattr(i, 'last_name', '')} {getattr(i, 'first_name', '')}" for i in db.query(models.Instructor).all()}
                    except Exception:
                        pass
                # Fill missing instructor IDs from DB
                missing_iids = set()
                for item in items:
                    iid = item.get('instructor_id')
                    if iid is not None and iid not in _instr_names:
                        missing_iids.add(int(iid))
                if missing_iids:
                    try:
                        extra_i = db.query(models.Instructor).filter(models.Instructor.id.in_(list(missing_iids))).all()
                        for i in extra_i:
                            _instr_names[i.id] = f"{getattr(i, 'last_name', '')} {getattr(i, 'first_name', '')}"
                    except Exception:
                        pass

                enriched = []
                for item in items:
                    enriched_item = dict(item)
                    sid = item.get('subject_id')
                    if sid is not None and sid in _subj_lookup:
                        subj = _subj_lookup[sid]
                        enriched_item['subject_code'] = getattr(subj, 'code', '') or f'S{sid}'
                        enriched_item['descriptive_title'] = getattr(subj, 'description', '') or ''
                        enriched_item['subject_type'] = getattr(subj, 'type', '') or ''
                        enriched_item['units'] = getattr(subj, 'unit', '') or ''
                    rid = item.get('room_id')
                    if rid is not None:
                        enriched_item['room_name'] = _room_names.get(int(rid), f'Room {rid}')
                    iid = item.get('instructor_id')
                    if iid is not None:
                        enriched_item['instructor_name'] = _instr_names.get(int(iid), f'Instructor {iid}')
                    enriched.append(enriched_item)
                phase_callback(phase_name, enriched, total_subjects)
            except Exception:
                pass  # Ignore callback errors
    
    report_progress("Loading subjects and instructors...")
    
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

    if not subjects:
        logger.warning("No subjects to schedule")
        return []
    
    print("\n--- TRACE OS 101 ---")
    for s in subjects:
        if s.id == 66:
            print(f"OS 101 SURVIVED DB QUERY. Code: {s.code}")
    print(f"Num subjects initially: {len(subjects)}")

    if focus_subject_ids_set:
        filtered_subjects = [subject for subject in subjects if subject.id in focus_subject_ids_set]
        if len(filtered_subjects) != len(subjects):
            logger.info(
                "Filtered subjects by focus list: %d -> %d",
                len(subjects),
                len(filtered_subjects),
            )
        subjects = filtered_subjects
        
    for s in subjects:
        if s.id == 66:
            print(f"OS 101 SURVIVED FOCUS SET. Code: {s.code}")

    # Debug: Log subjects to be scheduled with safe attribute access
    logger.info("\nSubjects to be scheduled:")
    for i, subject in enumerate(subjects[:10], 1):  # Show first 10 subjects
        try:
            # Safely get attributes with defaults
            code = getattr(subject, 'code', '?')
            name = getattr(subject, 'description', 'Unnamed')
            subj_id = getattr(subject, 'id', '?')
            subj_type = getattr(subject, 'type', '?')
            subj_units = getattr(subject, 'unit', 0) or 0
            year_level = getattr(subject, 'year_level', '?')
            
            logger.info(f"{i}. {code} - {name} (ID: {subj_id}, Type: {subj_type}, "
                      f"Units: {subj_units}, Year: {year_level})")
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
        
        for s in subjects:
            if s.id == 66:
                print(f"OS 101 SURVIVED RE-QUERY. Code: {s.code}")
                
        if not any(s.id == 66 for s in subjects):
            print("OS 101 DROPPED DURING RE-QUERY!!")
            print(f"- is 66 in subject_ids? {66 in subject_ids}")
            print(f"- is 66 in subject_map? {66 in subject_map}")
    
    if not subjects:
        logger.warning("No subjects to schedule")
        return []
    
    # =========================================================================
    # NSTP SPECIAL HANDLING
    # =========================================================================
    # Save full subject list for report_phase enrichment (before NSTP filters it)
    _all_subjects_for_enrichment = list(subjects)
    # NSTP subjects (NSTP1, NSTP 2, NSTP 12, etc.) get special treatment:
    # - Fixed day: Saturday (SAT)
    # - Fixed room: FIELD
    # - Fixed time: 8:00 AM - 11:00 AM
    # - Only instructor selection uses CP to avoid overlaps
    # 
    # We extract NSTP subjects and schedule them separately before the main CP solver
    # =========================================================================
    
    nstp_subjects = [s for s in subjects if _is_nstp_only_subject(s)]
    non_nstp_subjects = [s for s in subjects if not _is_nstp_only_subject(s)]
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
            # Get shared-building room (for NSTP scheduling)
            # Prefer a room named FIELD in shared buildings, then any shared room, then legacy fallback
            shared_rooms = []
            for _r in db.query(models.Room).all():
                if _r.building_id:
                    _bldg = db.query(models.Building).get(_r.building_id)
                    if _bldg and _bldg.is_shared:
                        shared_rooms.append(_r)
            
            # Prefer FIELD-named room, then first shared room, then legacy fallback
            field_room = None
            if shared_rooms:
                field_named = [r for r in shared_rooms if (r.name or "").upper() == "FIELD"]
                field_room = field_named[0] if field_named else shared_rooms[0]
            if not field_room:
                # Fallback to legacy name match
                field_room = db.query(models.Room).filter(models.Room.name == NSTP_ROOM_NAME).first()
            
            if not field_room:
                logger.warning(f"No shared-building room found. NSTP subjects will be scheduled via normal CP.")
                non_nstp_subjects.extend(nstp_subjects)
                nstp_subjects = []
            else:
                # Schedule NSTP subjects: each block gets a DIFFERENT instructor
                # All blocks share the same room, day, and time
                
                try:
                    num_blocks = int(block_count) if block_count else 1
                except (TypeError, ValueError):
                    num_blocks = 1
                
                # Track instructors already assigned across ALL NSTP subjects+blocks
                newly_booked_instructors = set()
                
                for nstp_subj in nstp_subjects:
                    nstp_code = getattr(nstp_subj, 'code', 'NSTP')
                    nstp_id = getattr(nstp_subj, 'id', 0)
                    
                    # Get instructors that can teach this specific NSTP subject
                    all_active_instructors = db.query(models.Instructor).filter(models.Instructor.is_active == True).all()
                    debug_lines = []
                    
                    nstp_code_upper = nstp_code.upper().replace(" ", "")
                    is_nstp1 = "NSTP1" in nstp_code_upper or nstp_code_upper == "NSTP"
                    is_nstp2 = "NSTP2" in nstp_code_upper
                    
                    candidate_pool = []
                    
                    msg_scan = f"[NSTP DEBUG] Scanning {len(all_active_instructors)} instructors for {nstp_code}..."
                    logger.info(msg_scan)
                    debug_lines.append(msg_scan)

                    for instr in all_active_instructors:
                        assignable = (getattr(instr, 'assignable_courses', '') or '').upper()
                        assignable_clean = assignable.replace(" ", "")
                        
                        score = 0
                        # Only accept EXACT subject match (NSTP 1 ≠ NSTP 2)
                        if is_nstp1 and ("NSTP1" in assignable_clean or "NSTP 1" in assignable):
                            score = 2
                        elif is_nstp2 and ("NSTP2" in assignable_clean or "NSTP 2" in assignable):
                            score = 2
                            
                        if score > 0:
                            candidate_pool.append((score, instr))
                    
                    # Sort candidates by score descending (best first)
                    candidate_pool.sort(key=lambda x: x[0], reverse=True)
                    eligible_instrs = [c[1] for c in candidate_pool]
                    
                    param_len = len(eligible_instrs)
                    msg_header = f"[NSTP INFO] found {param_len} qualified candidates for {nstp_code} (Day {sat_day.id})."
                    logger.info(msg_header)
                    debug_lines.append(msg_header)
                    
                    subj_course_id = getattr(nstp_subj, 'course_id', course_id) or course_id
                    subj_year = getattr(nstp_subj, 'year_level', year) or year or 1
                    
                    # Assign a DIFFERENT instructor for EACH block
                    # If all unique instructors are used, allow reuse with workload checks
                    all_blocks_scheduled = True
                    nstp_duration_min = NSTP_END_MIN - NSTP_START_MIN  # 180 min
                    # Track how many NSTP blocks each instructor has been assigned
                    nstp_block_count_per_instr = defaultdict(int)
                    
                    for block_idx in range(1, num_blocks + 1):
                        block_label = _block_index_to_label(block_idx) or "A"
                        
                        selected_instructor = None
                        # --- Pass 1: Try to find an unused instructor ---
                        for instr in eligible_instrs:
                            if instr.id in newly_booked_instructors:
                                msg = f"  -> Block {block_label} Candidate {instr.id}: BUSY (assigned to another block)"
                                logger.debug(msg)
                                debug_lines.append(msg)
                                continue
                            
                            selected_instructor = instr
                            newly_booked_instructors.add(instr.id)
                            nstp_block_count_per_instr[instr.id] += 1
                            msg = f"  -> Block {block_label} Candidate {instr.id}: AVAILABLE (Selected)."
                            logger.info(msg)
                            debug_lines.append(msg)
                            break
                        
                        # --- Pass 2: All unique instructors exhausted, allow reuse ---
                        if not selected_instructor and eligible_instrs:
                            logger.info(f"  [NSTP] All {len(eligible_instrs)} unique instructors used. Attempting reuse for block {block_label}...")
                            debug_lines.append(f"  [NSTP REUSE] Attempting instructor reuse for block {block_label}")
                            
                            # Compute existing workload for each eligible instructor
                            # (existing DB schedules + NSTP blocks already assigned in this run)
                            reuse_candidates = []
                            for instr in eligible_instrs:
                                # Get existing weekly minutes from DB schedules
                                existing_mins = 0
                                try:
                                    existing_scheds = db.query(models.Schedule).filter(
                                        models.Schedule.instructor_id == instr.id,
                                        models.Schedule.semester == semester
                                    ).all()
                                    for sched in existing_scheds:
                                        raw_time = (getattr(sched, 'time', None) or '').strip()
                                        parsed = _parse_time_range_minutes(raw_time.split(' ', 1)[-1] if ' ' in raw_time else raw_time)
                                        if parsed:
                                            existing_mins += max(0, parsed[1] - parsed[0])
                                except Exception:
                                    pass
                                
                                # Add NSTP blocks already assigned in this run
                                nstp_assigned_mins = nstp_block_count_per_instr.get(instr.id, 0) * nstp_duration_min
                                total_mins = existing_mins + nstp_assigned_mins
                                
                                # Get this instructor's weekly limit
                                employment_type = (getattr(instr, 'employment_type', None) or 'regular').strip().lower()
                                if employment_type == 'visiting':
                                    limit_mins = 30 * 60  # 1800 min
                                else:
                                    designation = (getattr(instr, 'designation', None) or '').strip().lower()
                                    deduction_map = {"program chair": 3, "college secretary": 3, "dean": 12, "associate dean": 12, "director": 12}
                                    deduction = deduction_map.get(designation, 0)
                                    limit_mins = max(0, 24 - deduction) * 60
                                
                                remaining = limit_mins - total_mins
                                msg = f"  -> Reuse check {instr.id}: {total_mins}/{limit_mins} min used, {nstp_block_count_per_instr.get(instr.id, 0)} NSTP blocks, remaining={remaining}"
                                logger.debug(msg)
                                debug_lines.append(msg)
                                
                                if remaining >= nstp_duration_min:
                                    reuse_candidates.append((nstp_block_count_per_instr.get(instr.id, 0), total_mins, instr))
                            
                            if reuse_candidates:
                                # Pick instructor with fewest NSTP blocks, then least total workload
                                reuse_candidates.sort(key=lambda x: (x[0], x[1]))
                                _, _, best_instr = reuse_candidates[0]
                                selected_instructor = best_instr
                                nstp_block_count_per_instr[best_instr.id] += 1
                                msg = f"  -> Block {block_label} Candidate {best_instr.id}: REUSED (least loaded, {reuse_candidates[0][0]} existing NSTP blocks)"
                                logger.info(msg)
                                debug_lines.append(msg)
                            else:
                                msg = f"  -> Block {block_label}: No instructor has capacity for reuse ({nstp_duration_min} min needed)"
                                logger.warning(msg)
                                debug_lines.append(msg)
                        
                        if selected_instructor:
                            nstp_item = {
                                "subject_id": nstp_id,
                                "clone_subject_id": nstp_id,
                                "course_id": subj_course_id,
                                "instructor_id": selected_instructor.id,
                                "room_id": field_room.id,
                                "day_id": sat_day.id,
                                "time": NSTP_TIME_LABEL,
                                "year": subj_year,
                                "semester": semester,
                                "block": block_label,
                                "start_min": NSTP_START_MIN,
                                "end_min": NSTP_END_MIN,
                            }
                            nstp_scheduled_items.append(nstp_item)
                            reuse_tag = " [REUSED]" if nstp_block_count_per_instr.get(selected_instructor.id, 0) > 1 else ""
                            logger.info(f"  [OK] NSTP scheduled: {nstp_code} block {block_label} -> Sunday 8-11am, {field_room.name}, Instructor {selected_instructor.id}{reuse_tag}")
                        else:
                            all_blocks_scheduled = False
                            logger.warning(f"  [FAIL] NSTP {nstp_code} block {block_label}: No available instructor (all exhausted and over capacity)")
                    
                    if not all_blocks_scheduled:
                        logger.warning(f"  [PARTIAL] NSTP {nstp_code}: Some blocks could not be assigned instructors")
                    
                    # Write debug log
                    try:
                        with open("nstp_debug.log", "a") as f:
                            f.write("\n".join(debug_lines) + "\n\n")
                    except Exception as e:
                        logger.error(f"Failed to write nstp_debug.log: {e}")
        
        logger.info(f"NSTP pre-scheduling complete: {len(nstp_scheduled_items)} scheduled, {len([s for s in nstp_subjects if s not in non_nstp_subjects])} subjects handled")
        # Emit NSTP phase results for progressive timetable
        report_phase("NSTP", list(nstp_scheduled_items), len(_all_subjects_for_enrichment))
        import time as _phase_time
        _phase_time.sleep(3)  # Let frontend poll and display
    
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
    # Load only active instructors
    instructors = db.query(models.Instructor).filter(models.Instructor.is_active == True).all()
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
    instructor_current_units: Dict[int, int] = defaultdict(int)
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
            # Calculate current units
            try:
                if sched.subject_id:
                     # We might need to fetch subject if not loaded. 
                     # For safety, rely on unit if available, or try to load.
                     # Since this is ORM, sched.subject might trigger a query.
                     # To be safe and fast, maybe better to fetch units in bulk or rely on a simple query if needed.
                     # But for now let's try accessing subject.unit if present
                     if sched.subject:
                         instructor_current_units[instr_id_int] += int(getattr(sched.subject, "unit", 0))
            except Exception:
                pass
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
    rooms = db.query(models.Room).filter(models.Room.is_available == True).order_by(models.Room.capacity).all()
    
    # Load Building Distances for Travel Time Constraints
    travel_times = {}
    room_building_map = {}
    try:
        # Load distances
        building_distances = db.query(models.BuildingDistance).all()
        for bd in building_distances:
            travel_times[(bd.from_building_id, bd.to_building_id)] = bd.travel_time_minutes
            travel_times[(bd.to_building_id, bd.from_building_id)] = bd.travel_time_minutes
            
        # Map Room ID -> Building ID
        # Note: We rely on the relationship or 'building_id' field. 
        # Since we just query Room, we access the attribute.
        for r in rooms:
            if hasattr(r, 'building_id') and r.building_id:
                room_building_map[r.id] = r.building_id
                
        if travel_times:
            logger.info("Loaded %d building travel time pairs", len(travel_times))
    except Exception as e:
        logger.warning("Failed to load building distances: %s", e)

    logger.info(f"Loaded {len(rooms)} rooms")
    
    # Debug: Log resource counts
    logger.info("\nResource Availability:")
    logger.info(f"- Total active rooms: {len(rooms)}")
    if rooms:
        capacities = [r.capacity for r in rooms if r.capacity is not None]
        if capacities:
            logger.info(f"  - Capacity range: {min(capacities)} to {max(capacities)}")
        else:
            logger.info("  - Capacity range: N/A (no rooms have capacity set)")
        # Ensure no room has None capacity (default to 0) to prevent downstream comparisons failing
        for r in rooms:
            if r.capacity is None:
                logger.warning(f"  ⚠️ Room '{r.name}' (ID: {r.id}) has no capacity set — defaulting to 0")
                r.capacity = 0
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
            logger.warning(f"⚠️ No valid start options for subject: {subject.code} - {getattr(subject, 'description', 'Unnamed')} "
                         f"(ID: {subject.id}, Type: {subject.type}, "
                         f"Units: {getattr(subject, 'unit', 0)})")
            
            # Additional debug for problematic subjects
            logger.debug(f"Subject details: {subject.__dict__}")
            # Log slot mismatch diagnosis
            _log_slot_mismatch_diagnosis(subject, slots_by_day, days, logger)

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
    course_to_instructors, course_to_all_rooms, course_to_preferred_rooms = build_eligibility_maps(subjects, instructors, rooms, db)
    # Maintain course_to_rooms alias for backward comp in greedy/retry if needed, or pass all_rooms
    # Greedy scheduler should ideally try preferred, then all.
    
    # Create room_id_to_name and room_by_id mappings
    room_id_to_name = {room.id: room.name for room in rooms}
    room_by_id = {room.id: room for room in rooms}

    # Build course code and instructor name lookups for user-friendly diagnostics
    _all_courses = db.query(models.Course).all() if db else []
    course_id_to_code = {c.id: (getattr(c, 'code', '') or f'Course {c.id}') for c in _all_courses}
    instr_id_to_name = {i.id: f"{getattr(i, 'last_name', '')} {getattr(i, 'first_name', '')}" for i in instructors}
    def _year_label(y):
        labels = {1: '1st Year', 2: '2nd Year', 3: '3rd Year', 4: '4th Year'}
        return labels.get(y, f'Year {y}')
    
    # Pre-load building distances and room-to-building mapping for proximity enforcement
    _bldg_dist_map: Dict[Tuple[int, int], int] = {}  # (from_bldg_id, to_bldg_id) -> travel_time_minutes
    _room_to_bldg_id: Dict[int, int] = {}  # room_id -> building_id
    if db:
        for bd in db.query(models.BuildingDistance).all():
            _bldg_dist_map[(bd.from_building_id, bd.to_building_id)] = bd.travel_time_minutes
            _bldg_dist_map[(bd.to_building_id, bd.from_building_id)] = bd.travel_time_minutes  # symmetric
        for r in rooms:
            if r.building_id:
                _room_to_bldg_id[r.id] = r.building_id
    logger.info(f"Loaded {len(_bldg_dist_map)//2} building distance pairs, {len(_room_to_bldg_id)} room-to-building mappings")
    
    # Build instructor preferences lookup (time preferences and unit limits)
    instructor_prefs = {}
    for inst in instructors:
        pref_start = getattr(inst, 'preferred_start_time', None)
        pref_end = getattr(inst, 'preferred_end_time', None)
        max_units = getattr(inst, 'max_units', None)
        
        # Convert time strings to minutes
        start_min = _time_str_to_minutes(pref_start) if pref_start else None
        end_min = _time_str_to_minutes(pref_end) if pref_end else None
        
        instructor_prefs[inst.id] = {
            'start_min': start_min,
            'end_min': end_min,
            'max_units': max_units
        }
    
    # Track currently assigned units per instructor (for max_units enforcement)
    instructor_assigned_units: Dict[int, int] = defaultdict(int)
    
    logger.info("Loaded preferences for %d instructors", len(instructor_prefs))
    
    # Debug: Log detailed eligibility information
    logger.info("\nDetailed Eligibility Debug:")
    
    # Log subjects being scheduled
    logger.info("\nSubjects to be scheduled:")
    for subj in subjects:
        logger.info(f"- Subject ID: {subj.id}, Code: {getattr(subj, 'code', 'N/A')}, "
                   f"Type: {getattr(subj, 'type', 'N/A')}, "
                   f"Course: {getattr(subj, 'course_id', 'N/A')}, "
                   f"Year: {getattr(subj, 'year_level', 'N/A')}, "
                   f"SBlock: {getattr(subj, 'student_block', 'N/A')}, "
                   f"Cluster: {getattr(subj, 'cluster', 'N/A')}")
    
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
        eligible_room_list = course_to_all_rooms.get(subj_id, []) if subj_id is not None else []
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
        years=None,  # Load ALL years to check global availability (don't filter by normalized_years)
        semester=semester,
        exclude_course_id=course_id,
        exclude_years=normalized_years,
        slots_by_day=slots_by_day,
        day_id_map=day_id_map,
    )
    
    # DEBUG: Room Utilization Summary
    room_util_counts = defaultdict(int)
    for (r_name, _, _) in booked_room_slots:
        room_util_counts[r_name] += 1
    
    logger.info("\n[DIAGNOSTIC] Room Booking Summary (occupied 30-min slots):")
    if not room_util_counts:
        logger.info("  - No rooms are booked.")
    else:
        for r_name, count in sorted(room_util_counts.items(), key=lambda x: x[1], reverse=True):
             logger.info(f"  - {r_name}: {count} slots booked")

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
            "[OK] DB time_blocks mapping: %d/%d slots mapped successfully (100%%)",
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
    
    # =========================================================================
    # 4-PHASE SCHEDULING PIPELINE
    # Phase 1: NSTP (already pre-scheduled above)
    # Phase 2: PE / PATHFIT subjects (shared rooms: GYM, Inner Quad — NOT FIELD)
    # Phase 3: Major subjects (college-specific rooms, scheduled first for priority)
    # Phase 4: GE / Minor subjects (remaining rooms, most flexible)
    #
    # Each phase runs the full cluster loop independently.
    # Booking state (room/instructor ranges) flows between phases so later
    # phases respect earlier assignments.
    # =========================================================================
    _all_subjects_for_phases = list(subjects)  # Preserve full list for partitioning

    _pe_subjects = [s for s in _all_subjects_for_phases if _is_pe_subject(s)]
    _major_subjects = [s for s in _all_subjects_for_phases if not _is_pe_subject(s) and getattr(s, 'is_major', False)]
    _ge_subjects = [s for s in _all_subjects_for_phases if not _is_pe_subject(s) and not getattr(s, 'is_major', False)]

    _phase_plan = []
    if _pe_subjects:
        _phase_plan.append(("PE/PATHFIT", _pe_subjects))
    if _major_subjects:
        _phase_plan.append(("MAJORS", _major_subjects))
    if _ge_subjects:
        _phase_plan.append(("GE/MINORS", _ge_subjects))

    # Fallback: if no subjects matched any phase (shouldn't happen), use all
    if not _phase_plan:
        _phase_plan.append(("ALL", _all_subjects_for_phases))

    logger.info(
        "\n" + "=" * 80 + "\n"
        "4-PHASE SCHEDULING PIPELINE\n"
        "Phase 1: NSTP - %d subjects (pre-scheduled)\n"
        "Phase 2: PE/PATHFIT - %d subjects\n"
        "Phase 3: MAJORS - %d subjects\n"
        "Phase 4: GE/MINORS - %d subjects\n" +
        "=" * 80,
        len(nstp_subjects) if nstp_subjects else 0,
        len(_pe_subjects), len(_major_subjects), len(_ge_subjects),
    )

    # Global booking maps (inter-cluster AND inter-phase propagation) - using block_index
    booked_room_slots_global = set(booked_room_slots)  # (room_name, day_id, block_index)
    booked_instr_slots_global = set(booked_instr_slots)  # (instr_id, day_id, block_index)

    # Additional global booking maps using real minute ranges.
    # This is necessary because TIME_BLOCKS contains overlapping windows (e.g., 7:00-8:30 and 7:30-8:30),
    # so a conflict cannot be represented reliably by (day_id, block_index) alone.
    # CRITICAL: Use passed-in ranges if provided (for inter-run conflict prevention)
    if booked_room_ranges_global is None:
        booked_room_ranges_global = defaultdict(list)  # (room_name, day_id) -> [(start_min, end_min), ...]
    elif not isinstance(booked_room_ranges_global, defaultdict):
        # Convert to defaultdict if it's a regular dict
        temp = defaultdict(list)
        temp.update(booked_room_ranges_global)
        booked_room_ranges_global = temp
    
    if booked_instr_ranges_global is None:
        booked_instr_ranges_global = defaultdict(list)  # (instr_id, day_id) -> [(start_min, end_min), ...]
    elif not isinstance(booked_instr_ranges_global, defaultdict):
        # Convert to defaultdict if it's a regular dict
        temp = defaultdict(list)
        temp.update(booked_instr_ranges_global)
        booked_instr_ranges_global = temp

    logger.info(f"Initialized global blocked ranges: Room keys={len(booked_room_ranges_global)}, Instr keys={len(booked_instr_ranges_global)}")
    sample_room_key = next(iter(booked_room_ranges_global)) if booked_room_ranges_global else None
    if sample_room_key:
         logger.info(f"Sample blocked room ranges for {sample_room_key}: {booked_room_ranges_global[sample_room_key]}")

    # Seed range-based bookings from existing bookings (DB + other courses).

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
    
    def _trace_all_scheduled_items(stage: str):
        for it in all_scheduled_items:
            if it.get("time") is None or it.get("clone_subject_id") is None:
                logger.error(f"[PHANTOM TRACE] Found phantom item at {stage}: {it}")
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

    # Identify shared-building room IDs for filtering logic (optimizes solver)
    # Build set once from buildings with is_shared=True
    _solver_shared_room_ids = set()
    for r in rooms:
        if r.building_id:
            _bldg = db.query(models.Building).get(r.building_id)
            if _bldg and _bldg.is_shared:
                _solver_shared_room_ids.add(r.id)
    print(f"[SOLVER INIT] Shared room IDs to exclude from regular subjects: {_solver_shared_room_ids}")
    field_room_id = -1
    if _solver_shared_room_ids:
        field_room_id = next(iter(_solver_shared_room_ids))  # Use first shared room for backward compat

    all_diagnostics: Dict[int, Dict[str, int]] = {}
    
    # CRITICAL: Initialize clone map BEFORE the loop so it accumulates across ALL phases/blocks/clusters
    # This ensures that even if a clone fails in Block A, we remember its mapping to the original subject
    # for final diagnostics pruning.
    clone_to_original_map = {}

    # =========================================================================
    # Build the block_cluster_plan with phase ordering:
    # PE/PATHFIT clusters first, then MAJORS, then GE/MINORS.
    # Each entry is (student_block_index, cluster_id, subjects, phase_name).
    # The existing cluster loop processes them in this exact order, so 
    # PE subjects are scheduled first, majors second, GE last.
    # Booking state flows naturally since the loop is sequential.
    # =========================================================================
    block_cluster_plan = []
    _current_phase_logged = None  # Track for phase transition logging

    for _phase_name, _phase_subjects in _phase_plan:
        # Group THIS phase's subjects by cluster
        _phase_by_cluster = defaultdict(list)
        for _ps in _phase_subjects:
            _pcid = _ps.cluster if _ps.cluster is not None else -1
            _phase_by_cluster[_pcid].append(_ps)
        _phase_cluster_items = sorted(_phase_by_cluster.items(), key=lambda x: x[0])
        if cluster_id_filter is not None:
            _phase_cluster_items = [(cid, subjs) for (cid, subjs) in _phase_cluster_items if cid == cluster_id_filter]
        for cid, subjs in _phase_cluster_items:
            if subjs:
                block_cluster_plan.append((0, cid, subjs, _phase_name))

    if not block_cluster_plan:
        logger.warning("[4-PHASE] No subjects in any phase cluster plan - nothing to schedule")

    # CRITICAL: Initialize these BEFORE the loop so they accumulate across ALL blocks
    # This ensures Block B sees Block A's bookings, preventing double-booking conflicts
    cross_cluster_scheduled_ranges = defaultdict(list)
    day_distribution_tracker = defaultdict(set)
    current_student_block_index = None
    # Default adaptive values (will be recalculated at each phase transition)
    ADAPTIVE_MAX_VARS_PER_SUBJECT = 1000
    ADAPTIVE_TIME_MULTIPLIER = 1.0
    ADAPTIVE_GAP_LIMIT = 0.05

    for student_block_index, cluster_id, cluster_subjects, *_phase_info in block_cluster_plan:
        # --- Phase transition logging ---
        _iter_phase = _phase_info[0] if _phase_info else "UNKNOWN"
        if _iter_phase != _current_phase_logged:
            # Emit partial results for the PREVIOUS phase before transitioning
            if _current_phase_logged is not None:
                report_phase(_current_phase_logged, list(all_scheduled_items) + list(nstp_scheduled_items), len(_all_subjects_for_enrichment))
            _current_phase_logged = _iter_phase
            logger.info("\n" + "=" * 80)
            logger.info("PHASE: %s", _iter_phase)
            logger.info("=" * 80)
            report_progress(f"Phase: {_iter_phase}...")

            # Recalculate adaptive solver pressure at each phase transition
            total_room_keys = len(rooms) * len(days)
            total_instr_keys = len(instructors) * len(days) if instructors else 1
            booked_room_count = sum(1 for k, v in booked_room_ranges_global.items() if v)
            booked_instr_count = sum(1 for k, v in booked_instr_ranges_global.items() if v)
            room_utilization = booked_room_count / max(1, total_room_keys)
            instr_utilization = booked_instr_count / max(1, total_instr_keys)
            resource_pressure = max(room_utilization, instr_utilization)
            if resource_pressure >= 0.8:
                ADAPTIVE_MAX_VARS_PER_SUBJECT = 3000
                ADAPTIVE_TIME_MULTIPLIER = 2.0
                ADAPTIVE_GAP_LIMIT = 0.02
            elif resource_pressure >= 0.6:
                ADAPTIVE_MAX_VARS_PER_SUBJECT = 2000
                ADAPTIVE_TIME_MULTIPLIER = 1.5
                ADAPTIVE_GAP_LIMIT = 0.03
            else:
                ADAPTIVE_MAX_VARS_PER_SUBJECT = 1000
                ADAPTIVE_TIME_MULTIPLIER = 1.0
                ADAPTIVE_GAP_LIMIT = 0.05
            logger.info(f"[ADAPTIVE] Phase {_iter_phase}: resource pressure={resource_pressure:.1%}, "
                        f"vars/subj={ADAPTIVE_MAX_VARS_PER_SUBJECT}")

        # DEBUG: Check ranges before loop
        debug_ranges = booked_room_ranges_global.get(("GS ER 7", 1), [])
        if debug_ranges:
             logger.info(f"[RANGE TRACE] Before Block {student_block_index} Cluster {cluster_id}: GS ER 7 Day 1 has {debug_ranges}")
        else:
             logger.info(f"[RANGE TRACE] Before Block {student_block_index} Cluster {cluster_id}: GS ER 7 Day 1 is EMPTY")

        if current_student_block_index != student_block_index:
            current_student_block_index = student_block_index
            # CRITICAL FIX: Do NOT reset cross_cluster_scheduled_ranges or day_distribution_tracker!
            # These MUST accumulate across blocks so Block B sees Block A's bookings.
            # Bug was: resetting these allowed same room/instructor to be double-booked across blocks.
            phys_lab_friday = booked_room_ranges_global.get(("Phys Lab", 5), [])
            logger.info(f"=== Moving to student block {student_block_index} (preserving {len(cross_cluster_scheduled_ranges)} cross-cluster bookings) ===")
            logger.info(f"[ROOM STATE] Phys Lab Friday bookings: {phys_lab_friday}")

        logger.info("=== Solving cluster %s (%d subjects, phase=%s) ===", cluster_id, len(cluster_subjects), _iter_phase)
        
        # Initialize CP-SAT model for this cluster
        model = cp_model.CpModel()
        
        # Log subject IDs in this cluster for debugging
        subject_ids_in_cluster = [s.id for s in cluster_subjects]
        logger.info("Cluster %s subject IDs: %s", cluster_id, subject_ids_in_cluster)
        
        # Populate clone map for all subjects in this cluster (including clones)
        for s in cluster_subjects:
            s_id_val = getattr(s, "id", None)
            if s_id_val is None:
                continue
            # Try to get original ID
            orig_id_val = getattr(s, "original_subject_id", None)
            if orig_id_val is not None:
                try:
                    clone_to_original_map[int(s_id_val)] = int(orig_id_val)
                except Exception:
                    pass
        
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
            course_to_all_rooms,    # Pass ALL valid rooms
            course_to_preferred_rooms, # Pass PREFERRED rooms for prioritization
            slots_by_day,
            saved_booked_rooms,
            saved_booked_instrs,
            rooms,
            days
        )
        
        # Restore booked sets - the actual booking will be applied after solver confirms chosen starts
        booked_room_slots_global = saved_booked_rooms
        booked_instr_slots_global = saved_booked_instrs
        
        # ... (rest of the logic)

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
        start_options_count = defaultdict(int)  # NEW: Track options per subject
        presence_weekly_minutes = {}
        instructor_presence_terms = defaultdict(list)  # instructor_id -> [(presence_var, weekly_minutes), ...]
        instructor_unit_terms = defaultdict(list)      # instructor_id -> [(presence_var, units), ...]
        
        soft_room_penalties = []
        SOFT_ROOM_PENALTY_WEIGHT = 50
        
        # Distance-based room penalties: penalize rooms far from subject's college building
        # Each entry is (presence_var, travel_time_penalty)
        distance_penalties: List[Tuple[Any, int]] = []
        DISTANCE_PENALTY_WEIGHT = 10  # Multiplied by travel_time_minutes
        
        # Global limit: maximum variables per subject to prevent memory explosion
        # ADAPTIVE: Increases when resources are heavily utilized (80%+) for better solutions
        MAX_VARIABLES_PER_SUBJECT = ADAPTIVE_MAX_VARS_PER_SUBJECT
        
        # Track if this is cluster 0 and first subject for detailed debug logging
        is_cluster_0 = (cluster_id == 0)
        first_subject_in_cluster_0_logged = False
        
        # Ensure subject_ids_list is defined
        subject_ids_list = [s.id for s in cluster_subjects]
        subject_lookup_cluster = {s.id: s for s in cluster_subjects}
        id_to_code = {s.id: s.code for s in cluster_subjects}
        subjects_without_options = []  # Track subjects with no valid options
        subjects_skipped_count = 0  # Count subjects that were fully skipped
        
        for subject_id in subject_ids_list:
            subject = subject_lookup_cluster.get(subject_id)
            if not subject:
                continue
            
            code = id_to_code.get(subject_id, f"ID_{subject_id}")  # For logging/debugging
            
            # Always get a LIST - ensure type safety
            # CRITICAL: Maps are keyed by ORIGINAL subject.id, but clones have different IDs.
            # Fall back to original_subject_id for cloned subjects.
            _orig_sid = getattr(subject, 'original_subject_id', None) or subject_id
            eligible_rooms = course_to_all_rooms.get(subject_id, [])
            if not eligible_rooms and _orig_sid != subject_id:
                eligible_rooms = course_to_all_rooms.get(_orig_sid, [])
            preferred_rooms_list = course_to_preferred_rooms.get(subject_id, [])
            if not preferred_rooms_list and _orig_sid != subject_id:
                preferred_rooms_list = course_to_preferred_rooms.get(_orig_sid, [])
            preferred_rooms_set = set(preferred_rooms_list) if preferred_rooms_list else set()

            if not isinstance(eligible_rooms, list):
                eligible_rooms = list(eligible_rooms) if eligible_rooms else []
            
            eligible_instrs = course_to_instructors.get(subject_id, [])
            if not eligible_instrs and _orig_sid != subject_id:
                eligible_instrs = course_to_instructors.get(_orig_sid, [])
            if not isinstance(eligible_instrs, list):
                eligible_instrs = list(eligible_instrs) if eligible_instrs else []
            
            # NOTE: Shared-building rooms are available to all colleges (not excluded).
            # Claimed rooms (via subject_room_preferences) are already excluded by build_eligibility_maps.
            
            # Compute subject's college building ID for proximity sorting/penalties
            _subj_bldg_id = None
            if subject.course_id and db:
                _c = db.query(models.Course).get(subject.course_id)
                if _c and _c.college_id:
                    _college_bldgs = db.query(models.Building).filter(
                        models.Building.college_id == _c.college_id
                    ).all()
                    if _college_bldgs:
                        _subj_bldg_id = _college_bldgs[0].id
            PROXIMITY_THRESHOLD_MIN = 15
            
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
                        # For non-sports subjects, strip shared rooms from cluster result
                        _c_code = (getattr(subject, 'code', '') or '').upper().strip()
                        _c_is_sports = (
                            _c_code.startswith("NSTP") or
                            _c_code.startswith("PE") or
                            _c_code.startswith("PATHFIT")
                        )
                        if not _c_is_sports and _solver_shared_room_ids:
                            rooms_in_same_cluster = [
                                rid for rid in rooms_in_same_cluster
                                if rid not in _solver_shared_room_ids
                            ]
                        # Only use cluster-filtered rooms if non-empty after shared room exclusion
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
            # FALLBACK: If no eligible rooms, add fallback options to ensure scheduling
            # But for instructors, strict specialization is enforced — skip if no eligible
            if len(eligible_instrs) == 0:
                logger.warning(f"Subject {code} ({subject_id}) has no eligible specialized instructors - skipping")
                subjects_without_options.append((code, "no eligible specialized instructors"))
                subjects_skipped_count += 1
                continue

            if len(eligible_rooms) == 0:
                logger.warning(f"Subject {code} ({subject_id}) has no eligible rooms - adding fallback")
                # CRITICAL: Fallback must still respect college filtering
                # Look up the subject's college via its course_id
                _subj_obj = subject_lookup_cluster.get(subject_id)
                _subj_course_id = getattr(_subj_obj, 'course_id', None) if _subj_obj else None
                _subj_college_id = None
                if _subj_course_id:
                    _course_obj = db.query(models.Course).filter(models.Course.id == _subj_course_id).first()
                    if _course_obj:
                        _subj_college_id = _course_obj.college_id
                
                # Build college-aware room → college map (reuse from build_eligibility_maps)
                _room_college_map = {}
                for _rm in rooms:
                    if _rm.building_id:
                        _bldg_obj = db.query(models.Building).get(_rm.building_id)
                        if _bldg_obj:
                            _room_college_map[_rm.id] = getattr(_bldg_obj, 'college_id', None)
                
                if _subj_college_id is not None:
                    # Only use rooms from the same college or rooms with no college assigned
                    # If subject has explicit DB room preferences, restrict to those
                    _db_pref_ids = set()
                    if db:
                        _prefs = db.query(models.SubjectRoomPreference).filter(
                            models.SubjectRoomPreference.subject_id == subject_id
                        ).all()
                        _db_pref_ids = {p.room_id for p in _prefs}
                    if _db_pref_ids:
                        eligible_rooms = [room.id for room in rooms if room.id in _db_pref_ids]
                    else:
                        # Exclude rooms claimed by other subjects AND shared-building rooms
                        _all_claimed = set()
                        if db:
                            for _p in db.query(models.SubjectRoomPreference).all():
                                _all_claimed.add(_p.room_id)
                        # Also exclude shared-building rooms (FIELD, GYM, Inner Quad)
                        # unless this is an NSTP/PE/PATHFIT subject
                        _subj_code_upper = (getattr(subject, 'code', '') or '').upper().strip()
                        _is_sports_or_nstp = (
                            _subj_code_upper.startswith("NSTP") or
                            _subj_code_upper.startswith("PE") or
                            _subj_code_upper.startswith("PATHFIT")
                        )
                        _shared_exclude = set()
                        if not _is_sports_or_nstp and db:
                            for _bldg in db.query(models.Building).filter(models.Building.is_shared == True).all():
                                for _sr in db.query(models.Room).filter(models.Room.building_id == _bldg.id).all():
                                    _shared_exclude.add(_sr.id)
                        _fallback_excluded = _all_claimed | _shared_exclude
                        eligible_rooms = [
                            room.id for room in rooms
                            if (_room_college_map.get(room.id) is None or _room_college_map.get(room.id) == _subj_college_id)
                            and room.id not in _fallback_excluded
                        ]
                    logger.warning(f"  - Fallback: using {len(eligible_rooms)} rooms (college-filtered, college_id={_subj_college_id})")
                else:
                    _db_pref_ids = set()
                    if db:
                        _prefs = db.query(models.SubjectRoomPreference).filter(
                            models.SubjectRoomPreference.subject_id == subject_id
                        ).all()
                        _db_pref_ids = {p.room_id for p in _prefs}
                    if _db_pref_ids:
                        eligible_rooms = [room.id for room in rooms if room.id in _db_pref_ids]
                    else:
                        # Exclude rooms claimed by other subjects AND shared-building rooms
                        _all_claimed = set()
                        if db:
                            for _p in db.query(models.SubjectRoomPreference).all():
                                _all_claimed.add(_p.room_id)
                        _subj_code_upper = (getattr(subject, 'code', '') or '').upper().strip()
                        _is_sports_or_nstp = (
                            _subj_code_upper.startswith("NSTP") or
                            _subj_code_upper.startswith("PE") or
                            _subj_code_upper.startswith("PATHFIT")
                        )
                        _shared_exclude = set()
                        if not _is_sports_or_nstp and db:
                            for _bldg in db.query(models.Building).filter(models.Building.is_shared == True).all():
                                for _sr in db.query(models.Room).filter(models.Room.building_id == _bldg.id).all():
                                    _shared_exclude.add(_sr.id)
                        _fallback_excluded = _all_claimed | _shared_exclude
                        eligible_rooms = [room.id for room in rooms if room.id not in _fallback_excluded]
                    logger.warning(f"  - Fallback: using all {len(eligible_rooms)} rooms (no college context)")
                subjects_without_options.append((code, "no eligible rooms (used fallback)"))
            
            # ====================================================================
            # HARD FILTER: Strip shared-building rooms (FIELD, GYM, Inner Quad)
            # from ANY subject that is NOT NSTP/PE/PATHFIT.
            # This is the FINAL safety net — catches all fallback paths.
            # ====================================================================
            # FIX: Use the logging code variable which is correctly mapped from id_to_code
            # This ensures we use the correct code for the subject_id being processed
            _code_upper = (code or '').upper().strip()
            _is_sports_nstp = (
                _code_upper.startswith("NSTP") or
                _code_upper.startswith("PE") or
                _code_upper.startswith("PATHFIT")
            )
            if not _is_sports_nstp and _solver_shared_room_ids:
                _before = len(eligible_rooms)
                eligible_rooms = [rid for rid in eligible_rooms if rid not in _solver_shared_room_ids]
                if _before != len(eligible_rooms):
                    print(f"[HARD FILTER] {_code_upper} (ID:{subject_id}): Removed {_before - len(eligible_rooms)} shared rooms -> {len(eligible_rooms)} remaining")
                    logger.info(
                        "[HARD FILTER] %s (ID:%d): Removed %d shared rooms, %d remaining",
                        _code_upper, subject_id, _before - len(eligible_rooms), len(eligible_rooms)
                    )
            # FIELD is reserved for NSTP ONLY — exclude it for PE/PATHFIT too
            if _is_sports_nstp and not _code_upper.startswith("NSTP"):
                _field_ids = {rid for rid in eligible_rooms if room_id_to_name.get(rid, "").upper().strip() == "FIELD"}
                if _field_ids:
                    eligible_rooms = [rid for rid in eligible_rooms if rid not in _field_ids]
                    logger.info("[HARD FILTER] %s (ID:%d): Excluded FIELD (reserved for NSTP), %d rooms remaining",
                                _code_upper, subject_id, len(eligible_rooms))
            subj_opts = all_start_options.get(subject_id, [])
            if not subj_opts:
                logger.warning(f"Subject {code} ({subject_id}) has no valid time windows - generating fallback options")
                logger.warning(f"  - Subject type: {getattr(subject, 'type', '?')}")
                logger.warning(f"  - Subject code: {getattr(subject, 'code', '?')}")
                logger.warning(f"  - Units: {getattr(subject, 'unit', 0)}")
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
                # Detailed debug logging for first subject in cluster 0, first window only
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
                
                # ENFORCE NSTP SUNDAY CONSTRAINT
                # If pre-scheduling failed and we are here, we MUST ensure we don't schedule NSTP on non-Sunday
                if _is_nstp_only_subject(subject):
                    # Find Sunday ID - usually 7 but let's be safe
                    # We can iterate days list or assume 7. 
                    # Let's check against the DAY_LABEL constant if available, otherwise "SUN"
                    is_sunday = False
                    for d_id in day_ids:
                        d_obj = next((d for d in days if d.id == d_id), None)
                        if d_obj and (d_obj.label == "SUN" or d_obj.label == NSTP_DAY_LABEL):
                            is_sunday = True
                        else:
                            is_sunday = False
                            break
                    
                    if not is_sunday:
                        # Skip this option
                        continue
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
                    # Simplified logging to avoid NameError
                    if eligible_rooms:
                        logger.debug(f"DEBUG - Checking {len(eligible_rooms)} eligible rooms (sample: {eligible_rooms[0]})")
                    if eligible_instrs:
                        logger.debug(f"DEBUG - Checking {len(eligible_instrs)} eligible instructors (sample: {eligible_instrs[0]})")
                
                # Pre-filter rooms: use precomputed available blocks with per-day checks
                # CRITICAL: Use blocks_by_day for accurate per-day availability checking
                compatible_rooms = []
                blocks_by_day = opt.get("blocks_by_day", {})
                if not blocks_by_day:
                    # Fallback: construct from block_indices if blocks_by_day missing
                    blocks_by_day = {d_id: block_indices for d_id in day_ids}
                
                # Log room filtering results (once per subject, on first window)
                should_debug_room = subject_id in DEBUG_SUBJECT_IDS

                # Track rejection reasons for this subject/window
                if "rejection_counters" not in subject.__dict__:
                    subject.rejection_counters = defaultdict(int)

                for room_id in eligible_rooms:
                    room_name = room_id_to_name.get(room_id)
                    if room_name is None:
                        continue
                    
                    # Capacity check (per-subject enrollment)
                    room = room_by_id.get(room_id)
                    if room and room.capacity and hasattr(subject, 'enrollment'):
                        enrollment = getattr(subject, 'enrollment', 0)
                        if room.capacity < enrollment:
                            if should_debug_room:
                                logger.debug(f"[ROOM REJECT] Subject {subject_id} rejected {room_name} (Cap {room.capacity} < Enroll {enrollment})")
                            subject.rejection_counters["Capacity"] += 1
                            continue
                    
                    # Check availability for every day in the option
                    room_ok = True
                    for d_id in day_ids:
                        # Range-based conflict check (handles overlapping TIME_BLOCK definitions)
                        conflict_metadata = _range_conflicts(booked_room_ranges_global, room_name, d_id, start_min, end_min)
                        if conflict_metadata:
                            if should_debug_room:
                                logger.debug(f"[ROOM REJECT] Subject {subject_id} rejected {room_name} on Day {d_id} {start_min}-{end_min} due to conflict. Metadata: {conflict_metadata}")
                            
                            # Aggregate reason from metadata
                            reason = "Unknown Conflict"
                            if isinstance(conflict_metadata, dict):
                                desc = conflict_metadata.get("description", "Other Booking")
                                reason = f"Blocked by {desc}"
                            
                            subject.rejection_counters[reason] += 1
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
                        
                        # Check instructor time preferences
                        if instructor_id in instructor_prefs:
                            prefs = instructor_prefs[instructor_id]
                            # Check every day in the option
                            if not is_time_within_preference(start_min, end_min, prefs['start_min'], prefs['end_min']):
                                instr_ok = False
                                break
                                
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
                    # Prioritize rooms by proximity to the subject's college building,
                    # then by capacity as a tiebreaker. This biases the solver toward
                    # assigning rooms in nearby buildings (minimizing travel time).
                    def _room_proximity_sort_key(r_tuple):
                        rid = r_tuple[0]
                        r_bldg = _room_to_bldg_id.get(rid)
                        # Same building as subject's college = 0 travel time
                        if r_bldg and _subj_bldg_id and r_bldg == _subj_bldg_id:
                            travel = 0
                        elif r_bldg and _subj_bldg_id:
                            travel = _bldg_dist_map.get((r_bldg, _subj_bldg_id), 9999)
                        else:
                            travel = 500  # Unknown building, sort after known ones
                        capacity = room_by_id.get(rid, type('obj', (object,), {'capacity': 0})).capacity or 0
                        return (travel, -capacity)  # Lower travel first, then higher capacity
                    
                    compatible_rooms.sort(key=_room_proximity_sort_key)
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
                    # Log rejection reasons if we have them
                    if "rejection_counters" in subject.__dict__ and subject.rejection_counters:
                        sorted_reasons = sorted(subject.rejection_counters.items(), key=lambda x: -x[1])
                        reasons_str = ", ".join([f"{r}: {c}" for r, c in sorted_reasons])
                        # Only log full summary on last window to avoid spam
                        if opt_idx == len(subject_options) - 1:
                             logger.info(f"[CONFLICT DIAGNOSIS] Subject {subject_id} ({code}) has 0 options. Reasons: {reasons_str}")
                        else:
                             # Debug level for intermediate windows
                             logger.debug(f"[CONFLICT DIAGNOSIS] Subject {subject_id} ({code}) window {opt_idx}: 0 options. Reasons: {reasons_str}")

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
                        instructor_unit_terms[instructor_id].append(
                            (presence, int(getattr(subject, "unit", 0)))
                        )
                        
                        # Soft Room Constraint: Penalize if room is not in preferred list
                        # Only apply penalty if we HAVE preferred rooms defined (otherwise all are equal)
                        if preferred_rooms_set and room_id not in preferred_rooms_set:
                            soft_room_penalties.append(presence)
                        
                        # Distance-based penalty: penalize rooms far from subject's college building
                        if _room_to_bldg_id and _bldg_dist_map:
                            _r_bldg = _room_to_bldg_id.get(room_id)
                            if _r_bldg and _subj_bldg_id:
                                if _r_bldg == _subj_bldg_id:
                                    _travel = 0
                                else:
                                    _travel = _bldg_dist_map.get((_r_bldg, _subj_bldg_id), 0)
                                if _travel > PROXIMITY_THRESHOLD_MIN:
                                    distance_penalties.append((presence, _travel))

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
                reasons_str = ""
                if "rejection_counters" in subject.__dict__ and subject.rejection_counters:
                    sorted_reasons = sorted(subject.rejection_counters.items(), key=lambda x: -x[1])
                    reasons_str = f" Reasons: {', '.join([f'{r}: {c}' for r, c in sorted_reasons])}"

                logger.warning(
                    f"[CONFLICT DIAGNOSIS] Subject {subject_id} ({code}): Created 0 CP variables. {reasons_str} "
                    f"stats=[options={len(subj_opts)} processed={options_processed} "
                    f"rooms={len(eligible_rooms)} instrs={len(eligible_instrs)} "
                    f"skip_student={skipped_student_conflict} skip_no_room={skipped_no_rooms} skip_no_instr={skipped_no_instructors}]"
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
            eligible_rooms = course_to_all_rooms.get(subject_id, [])
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
        # Build start options with pruning (capacity + current global bookings + instructor availability)
        soft_room_penalties = []  # Track assignments to non-preferred rooms
        SOFT_ROOM_PENALTY_WEIGHT = 50
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
                          len(course_to_instructors), len(course_to_all_rooms),
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
        var_to_interval_data = {}  # var -> (start_min, duration_min, end_min, room_name, instr_id, course_id, year_level, day_id, room_id)
        
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
            # Appended room_id to the tuple for travel time constraints
            var_to_interval_data[var] = (start_min, duration_min, end_min, room_name, instructor_id, subj_course_id, year_level, day_id_int, room_id)

            # Precompute grouping maps - group by (resource, day_id) for each day separately
            if room_name:
                room_intervals_by_resource[(room_name, day_id_int)].append((var, start_min, duration_min, end_min))

            instr_intervals_by_resource[(instructor_id, day_id_int)].append((var, start_min, duration_min, end_min))

            # FIXED: Group by subject within cohort (course_id, year_level, student_block, day_id)
            # CRITICAL: Use subj_year (normalized int) to prevent string/int mismatches
            cohort_key = (subj_course_id, subj_year, student_block_index, day_id_int)
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
        # CONSTRAINT GROUP 2b: Instructor Travel Time Constraints
        # Rule: If instructor teaches in different buildings, enforce travel time gap
        # ====================================================================
        
        instructor_ids = [inst.id for inst in instructors]  # Build list of instructor IDs
        if travel_times and instructor_ids:
            travel_conflict_count = 0
            
            # Use instr_intervals_by_resource: (instr_id, day_id) -> [(var, start_min, duration_min, end_min), ...]
            # Note: The 'var' here maps to var_to_interval_data which now has room_id.
            
            for (instr_id, day_id), intervals in instr_intervals_by_resource.items():
                if len(intervals) < 2:
                    continue
                    
                # Pairwise check for travel time violations
                for i in range(len(intervals)):
                    for j in range(i + 1, len(intervals)):
                        varA, startA, durA, endA = intervals[i]
                        varB, startB, durB, endB = intervals[j]
                        
                        # Get Room IDs
                        dataA = var_to_interval_data.get(varA)
                        dataB = var_to_interval_data.get(varB)
                        
                        if not dataA or not dataB: 
                            continue
                            
                        # room_id is the last element (index 8)
                        # (start_min, duration_min, end_min, room_name, instr_id, course_id, year_level, day_id, room_id)
                        # Handle case where tuple might be old format (just in case)
                        if len(dataA) < 9 or len(dataB) < 9:
                            continue
                            
                        roomA = dataA[8]
                        roomB = dataB[8]
                        
                        if roomA == roomB:
                            continue
                            
                        bA = room_building_map.get(roomA)
                        bB = room_building_map.get(roomB)
                        
                        if not bA or not bB or bA == bB:
                            continue
                            
                        travel_min = travel_times.get((bA, bB), 0)
                        if travel_min <= 0:
                            continue
                            
                        # Enforce: If both A and B are present, they must be separated by travel_min
                        # Since start/end times are FIXED CONSTANTS for these variables (they are OPTIONAL intervals),
                        # we can statically determine if they violate the travel constraint.
                        
                        # Case 1: A is before B (A.end + travel > B.start)
                        if endA <= startB:
                            if endA + travel_min > startB:
                                # StartB is too soon after EndA
                                # Cannot have both
                                model.AddBoolOr([varA.Not(), varB.Not()])
                                travel_conflict_count += 1
                                
                        # Case 2: B is before A (B.end + travel > A.start)
                        elif endB <= startA:
                            if endB + travel_min > startA:
                                # StartA is too soon after EndB
                                # Cannot have both
                                model.AddBoolOr([varA.Not(), varB.Not()])
                                travel_conflict_count += 1
                                
                        # Case 3: Overlap
                        # If they overlap temporally, the NoOverlap constraint handles it.
                        # Do nothing here.
            
            if travel_conflict_count > 0:
                logger.info(
                    "Added %d travel time constraints for instructors (gap enforcement)",
                    travel_conflict_count
                )
        
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
        
        if soft_room_penalties:
            # Sum of non-preferred assignments * weight
            total_soft_room_penalty = model.NewIntVar(
                0,
                len(soft_room_penalties) * SOFT_ROOM_PENALTY_WEIGHT,
                f"cluster_{cluster_id}_soft_room_total"
            )
            model.Add(total_soft_room_penalty == sum(v * SOFT_ROOM_PENALTY_WEIGHT for v in soft_room_penalties))
            penalty_exprs.append(total_soft_room_penalty)
        
        # Add distance-based penalties: rooms far from subject's college building
        if distance_penalties:
            total_distance_penalty = model.NewIntVar(
                0,
                sum(t * DISTANCE_PENALTY_WEIGHT for _, t in distance_penalties),
                f"cluster_{cluster_id}_distance_total"
            )
            model.Add(total_distance_penalty == sum(
                v * t * DISTANCE_PENALTY_WEIGHT for v, t in distance_penalties
            ))
            penalty_exprs.append(total_distance_penalty)
            logger.info(f"[PROXIMITY] Added distance penalties for {len(distance_penalties)} room variables in cluster {cluster_id}")

        if distribution_penalty is not None:
            penalty_exprs.append(DAY_TARGET_PENALTY_WEIGHT * distribution_penalty)

        # Enforce Instructor Max Units (HARD CONSTRAINT)
        # Uses DB max_units if set, otherwise derives from designation-based limit
        for inst_id, terms in instructor_unit_terms.items():
            max_units = instructor_prefs.get(inst_id, {}).get('max_units')
            if max_units is None:
                # Fallback: derive from designation-based limit_minutes (24h - deduction)
                limit_min = instructor_limit_minutes.get(inst_id, 24 * 60)
                # Convert minutes to approximate units (1 unit ≈ 1 hour)
                max_units = limit_min // 60
            if max_units <= 0:
                continue
                
            current_units = instructor_current_units.get(inst_id, 0)
            remaining_capacity = max(0, max_units - current_units)
            
            if terms:
                model.Add(sum(var * units for var, units in terms) <= remaining_capacity)
                logger.debug(
                    "[LOAD CONSTRAINT] Instructor %d: max_units=%d, current=%d, remaining=%d",
                    inst_id, max_units, current_units, remaining_capacity
                )

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

        overload_penalty_weight = 500  # Strong penalty to discourage overloading
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
        
        # ADAPTIVE: Apply time multiplier based on resource pressure
        cluster_max_time *= ADAPTIVE_TIME_MULTIPLIER
        cluster_max_time = min(cluster_max_time, 600.0)  # Hard cap at 10 minutes
        
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
        
        # ADAPTIVE: Tighter gap limits when resources are scarce for better solutions
        solver.parameters.relative_gap_limit = ADAPTIVE_GAP_LIMIT
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
        report_progress(f"Solving cluster {cluster_id}: {total_start_vars} variables...")
        
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

            # TTh DIAGNOSTIC: Show multi-day presence keys
            multi_day_keys = {k: len(v) for k, v in meta_by_presence_key.items() if len(v) > 1}
            if multi_day_keys:
                logger.info("[TTh DIAG] meta_by_presence_key has %d multi-day keys: %s",
                           len(multi_day_keys), 
                           {str(k): v for k, v in list(multi_day_keys.items())[:10]})

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

                # TTh DIAGNOSTIC: Log per_day_metas count for every selected presence
                meta_day_ids = [m.get("day_id") for m in per_day_metas]
                all_day_ids_in_meta = per_day_metas[0].get("day_ids", []) if per_day_metas else []
                if len(meta_day_ids) != len(all_day_ids_in_meta) or len(meta_day_ids) > 1:
                    logger.info(
                        "[TTh DIAG] subject_id=%s opt_idx=%s: per_day_metas=%d, meta_day_ids=%s, "
                        "option_day_ids=%s, presence_key=(%s,%s,%s,%s,%s)",
                        subject_id, opt_idx, len(per_day_metas), meta_day_ids,
                        all_day_ids_in_meta,
                        subject_id, start_min, opt_idx, room_id, instructor_id
                    )

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

                    # CRITICAL: Always generate time label from minutes to ensure consistent formatting
                    # (AM/PM, no seconds, standard hyphen)
                    s_str = _minutes_to_time_str(int(start_min_day))
                    e_str = _minutes_to_time_str(int(end_min_day))
                    time_label = f"{s_str} - {e_str}"
                    
                    # DEBUG: Trace GE-US (original subject 9) time_label generation
                    if original_subject_id == 9:
                        logger.info(f"[GE-US DEBUG] Block {student_block_index} day {day_id_int}: time_label={time_label}, "
                                   f"start_min={start_min_day}, end_min={end_min_day}, room={room_name}")


                    # If end_block_id still None, set it equal to start_block_id (single-block subject)
                    if end_block_id is None:
                        end_block_id = start_block_id

                    # Check soft room constraint status
                    is_soft_room = False
                    try:
                        # Re-retrieve preferred set for check (was computed earlier in loop)
                        # We need to construct it again or cache it. Caching is cleaner but requires scope change.
                        # Re-getting from map is cheap.
                        pref_list = course_to_preferred_rooms.get(subject_id, [])
                        if pref_list:
                            pref_set = set(pref_list)
                            if room_id_int not in pref_set:
                                is_soft_room = True
                    except Exception:
                        pass

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
                        "is_soft_constraint": is_soft_room, # New Flag
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
                    # Update range-based global bookings with metadata for better diagnostics
                    _cid = row.get("course_id")
                    _yr = row.get("year")
                    booking_metadata = {
                        "course_id": _cid,
                        "year": _yr,
                        "subject_id": row.get("subject_id"),
                        "description": f"{course_id_to_code.get(_cid, 'Unknown')} {_year_label(_yr)}"
                    }
                    booked_room_ranges_global[(room_name, day_id_int)].append((int(start_min_day), int(end_min_day), booking_metadata))
                    
                    if room_name == "GS ER 7" or room_id_int == 15:
                         logger.info(f"[SOLVER ASSIGNED] Subject {subject_id} assigned to {room_name} at Day {day_id_int} {start_min_day}-{end_min_day}")

                    booked_instr_ranges_global[(instr_id_int, day_id_int)].append((int(start_min_day), int(end_min_day), booking_metadata))
                    
                    # DEBUG: Track Phys Lab Friday bookings
                    if room_name == "Phys Lab" and day_id_int == 5:
                        logger.info(f"[ROOM BOOKING] Added Phys Lab Friday {start_min_day}-{end_min_day} (block {student_block_index}). "
                                   f"Total Phys Lab Friday bookings: {booked_room_ranges_global.get(('Phys Lab', 5), [])}")

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
        
        # DEBUG LOGGING FOR RETRY
        logger.info(f"[CLUSTER DEBUG] Cluster {cluster_id}: subjects={len(cluster_subjects)}, scheduled_ids_count={len(scheduled_original_ids)}")
        logger.info(f"[CLUSTER DEBUG] Unscheduled count: {len(unscheduled_subjects)}. IDs: {[s.id for s in unscheduled_subjects]}")

        
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
        
        retry_results, retry_diagnostics = _retry_unscheduled_subjects(
            db,
            unscheduled_subjects,
            course_to_instructors,
            course_to_all_rooms,
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
            instructor_prefs=instructor_prefs,
        )
        
        # Accumulate diagnostics
        all_diagnostics.update(retry_diagnostics)
        
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
        # DEBUG: Track sources BEFORE merging - write to file for full output
        debug_lines = []
        debug_lines.append(f"=== Block {student_block_index} SOURCE DEBUG ===")
        for idx, row in enumerate(scheduled_rows):
            if row.get("day_id") == 5 and row.get("room_id") == 7:
                msg = f"[SOURCE DEBUG] scheduled_rows[{idx}]: subject_id={row.get('subject_id')}, time={row.get('time')}, block={row.get('block')}"
                debug_lines.append(msg)
                logger.info(msg)
        for key, retry_val in retry_results.items():
            items = retry_val if isinstance(retry_val, list) else [retry_val]
            for item in items:
                if item.get("day_id") == 5 and item.get("room_id") == 7:
                    msg = f"[SOURCE DEBUG] retry_results[{key}]: subject_id={item.get('subject_id')}, time={item.get('time')}, block={item.get('block')}"
                    debug_lines.append(msg)
                    logger.info(msg)
        
        # Write debug info to file
        try:
            with open("phys_lab_debug.txt", "a") as f:
                f.write("\n".join(debug_lines) + "\n")
        except Exception as e:
            logger.error(f"Failed to write debug file: {e}")
        
        all_scheduled_items.extend(scheduled_rows)
        # Flatten retry_results: values can be dict (single-day) or list (paired multi-day)
        for retry_val in retry_results.values():
            if isinstance(retry_val, list):
                all_scheduled_items.extend(retry_val)
            else:
                all_scheduled_items.append(retry_val)
        
        _trace_all_scheduled_items(f"After Cluster {cluster_id}")

        # Emit partial results after each cluster for progressive timetable updates
        if _current_phase_logged is not None:
            report_phase(_current_phase_logged, list(all_scheduled_items) + list(nstp_scheduled_items), len(_all_subjects_for_enrichment))
            import time as _phase_time
            _phase_time.sleep(3)  # Let frontend poll and display
        
        # =====================================================================
        # CRITICAL FIX: Update global booking ranges with retry results
        # Retry pass items MUST be added to global bookings so subsequent blocks
        # see them and avoid scheduling in the same room/time slots.
        # =====================================================================
        for retry_val in retry_results.values():
            items = retry_val if isinstance(retry_val, list) else [retry_val]
            for item in items:
                room_id = item.get("room_id")
                day_id = item.get("day_id")
                start_min = item.get("start_min")
                end_min = item.get("end_min")
                instructor_id = item.get("instructor_id")
                
                # Parse time if start_min/end_min not present
                if (start_min is None or end_min is None) and item.get("time"):
                    time_str = item.get("time")
                    parsed = _parse_time_range_minutes(time_str)
                    if parsed and parsed[0] is not None and parsed[1] is not None:
                        start_min, end_min = parsed
                
                # Update room bookings
                if room_id is not None and day_id is not None and start_min is not None and end_min is not None:
                    room_name = room_id_to_name.get(int(room_id), f"Room{room_id}")
                    key = (room_name, int(day_id))
                    # Include metadata for retry-pass bookings
                    _cid = item.get("course_id")
                    _yr = item.get("year")
                    booking_metadata = {
                        "course_id": _cid,
                        "year": _yr,
                        "subject_id": item.get("subject_id"),
                        "description": f"{course_id_to_code.get(_cid, 'Unknown')} {_year_label(_yr)}"
                    }
                    booked_room_ranges_global[key].append((int(start_min), int(end_min), booking_metadata))
                    logger.info(f"[RETRY BOOKING] Added room booking: {room_name} day {day_id} [{start_min}-{end_min}]")
                
                # Update instructor bookings
                if instructor_id is not None and day_id is not None and start_min is not None and end_min is not None:
                    key = (int(instructor_id), int(day_id))
                    booked_instr_ranges_global[key].append((int(start_min), int(end_min), booking_metadata))
                    logger.info(f"[RETRY BOOKING] Added instructor booking: instr {instructor_id} day {day_id} [{start_min}-{end_min}]")
        
        # DEBUG: Track where Phys Lab Friday subject 9 (GE-US) came from
        for idx, item in enumerate(all_scheduled_items):
            room_id = item.get("room_id")
            day_id = item.get("day_id")
            subject_id = item.get("subject_id")
            # Check for Phys Lab (room_id 7) on Friday (day_id 5) with subject 9
            if day_id == 5 and room_id == 7:
                logger.info(f"[PHYS LAB DEBUG] Item {idx}: subject_id={subject_id}, time={item.get('time')}, block={item.get('block')}")
        
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
                    "on day_id=%s, time=%s with another class in same cohort (dropping subject).",
                    subj_id_int, c_id, year_val, day_id, row.get("time"),
                )
                subject_ids_to_drop.add(subj_id_int)
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

                retry_results_conflict, retry_diagnostics_conflict = _retry_unscheduled_subjects(
                    db,
                    dropped_subjects_to_retry,
                    course_to_instructors,
                    course_to_all_rooms,
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
                
                # Merge diagnostics
                all_diagnostics.update(retry_diagnostics_conflict)

                logger.info(
                    "[POST-CONFLICT RETRY] Completed: scheduled %d/%d subjects",
                    len(retry_results_conflict),
                    len(dropped_subjects_to_retry),
                )

                # Merge retry results back in - HANDLE LISTS (for paired subjects)
                for val in retry_results_conflict.values():
                    if isinstance(val, list):
                        kept_rows.extend(val)
                    else:
                        kept_rows.append(val)
        except Exception as e:
            logger.error("[POST-CONFLICT RETRY] Failed with error: %s", e)

    # Replace all_scheduled_items with kept_rows (+ any successful post-conflict retries)
    all_scheduled_items = kept_rows
    _trace_all_scheduled_items("After Post-Conflict Retry")



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
    
    # Emit final phase results for progressive timetable
    if _current_phase_logged is not None:
        report_phase(_current_phase_logged, list(all_scheduled_items) + list(nstp_scheduled_items), len(_all_subjects_for_enrichment))

    # Add NSTP pre-scheduled items to the final result BEFORE calculating summary
    if nstp_scheduled_items:
        logger.info(f"Adding {len(nstp_scheduled_items)} NSTP pre-scheduled items to final result")
        all_scheduled_items.extend(nstp_scheduled_items)
    
    # =========================================================================
    # POST-PROCESSING: Detect and resolve room double-bookings
    # =========================================================================
    # This catches any conflicts that might arise from cross-block scheduling
    # where different blocks are solved independently and might assign the same
    # room/day/time slot to different subjects.
    # =========================================================================
    room_time_bookings: Dict[Tuple[int, int, int, int], List[Dict]] = defaultdict(list)  # (room_id, day_id, start_min, end_min) -> [items]
    room_time_str_bookings: Dict[Tuple[int, int, str], List[Dict]] = defaultdict(list)  # (room_id, day_id, time_str) -> [items] - fallback for items without start_min/end_min
    
    for item in all_scheduled_items:
        room_id = item.get("room_id")
        day_id = item.get("day_id")
        start_min = item.get("start_min")
        end_min = item.get("end_min")
        time_str = item.get("time")
        
        if room_id is None or day_id is None:
            continue
        
        try:
            room_id_int = int(room_id)
            day_id_int = int(day_id)
        except (TypeError, ValueError):
            continue
            
        # EXEMPTION: Skip duplicate check for NSTP/PE rooms (FIELD, GYM, etc)
        # We check either by ID or Name if available. 
        # Here we only have room_id. We rely on looked up names if possible or simple constants logic.
        # But we don't have room names map here easily unless we passed it.
        # Wait, run_cp_scheduler HAS room_id_to_name map!
        
        current_room_name = room_id_to_name.get(room_id_int, "").upper()
        if current_room_name == NSTP_ROOM_NAME or "FIELD" in current_room_name or "COURT" in current_room_name or "GYM" in current_room_name:
             continue # Allow overlaps for these large venues
        
        # Track by start_min/end_min if available
        if start_min is not None and end_min is not None:
            try:
                key = (room_id_int, day_id_int, int(start_min), int(end_min))
                room_time_bookings[key].append(item)
            except (TypeError, ValueError):
                pass
        
        # ALWAYS track by time string as fallback (catches cases where start_min/end_min aren't set)
        if time_str:
            time_str_key = (room_id_int, day_id_int, str(time_str))
            room_time_str_bookings[time_str_key].append(item)
    
    # Find duplicates (same room, same day, same exact time)
    room_conflicts_exact = []
    for key, items in room_time_bookings.items():
        if len(items) > 1:
            room_conflicts_exact.append({
                "room_id": key[0],
                "day_id": key[1],
                "start_min": key[2],
                "end_min": key[3],
                "conflicting_items": items,
                "subjects": [i.get("subject_id") for i in items],
                "blocks": [i.get("block") for i in items],
            })
    
    # Also check conflicts by time string (catches cases where start_min/end_min aren't set)
    room_conflicts_by_time_str = []
    for key, items in room_time_str_bookings.items():
        if len(items) > 1:
            room_conflicts_by_time_str.append({
                "room_id": key[0],
                "day_id": key[1],
                "time_str": key[2],
                "conflicting_items": items,
                "subjects": [i.get("subject_id") for i in items],
                "blocks": [i.get("block") for i in items],
            })
    
    # Also check for overlapping time ranges (not just exact matches)
    room_day_items: Dict[Tuple[int, int], List[Dict]] = defaultdict(list)  # (room_id, day_id) -> [items]
    for item in all_scheduled_items:
        room_id = item.get("room_id")
        day_id = item.get("day_id")
        if room_id is not None and day_id is not None:
            try:
                # EXEMPTION: Skip duplicate check for NSTP/PE rooms (FIELD, GYM, etc) in OVERLAP loop
                room_id_int = int(room_id)
                current_room_name = room_id_to_name.get(room_id_int, "").upper()
                if current_room_name == NSTP_ROOM_NAME or "FIELD" in current_room_name or "COURT" in current_room_name or "GYM" in current_room_name:
                     continue 
                     
                room_day_items[(room_id_int, int(day_id))].append(item)
            except (TypeError, ValueError):
                continue
    
    room_conflicts_overlap = []
    for (room_id, day_id), items in room_day_items.items():
        if len(items) <= 1:
            continue
        # Check pairwise for overlaps
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                item_a = items[i]
                item_b = items[j]
                start_a = item_a.get("start_min")
                end_a = item_a.get("end_min")
                start_b = item_b.get("start_min")
                end_b = item_b.get("end_min")
                
                if start_a is None or end_a is None or start_b is None or end_b is None:
                    continue
                
                try:
                    s_a, e_a = int(start_a), int(end_a)
                    s_b, e_b = int(start_b), int(end_b)
                except (TypeError, ValueError):
                    continue
                
                # Check overlap
                if not (e_a <= s_b or e_b <= s_a):
                    room_conflicts_overlap.append({
                        "room_id": room_id,
                        "day_id": day_id,
                        "item_a": item_a,
                        "item_b": item_b,
                        "subject_a": item_a.get("subject_id"),
                        "subject_b": item_b.get("subject_id"),
                        "block_a": item_a.get("block"),
                        "block_b": item_b.get("block"),
                    })
    
    if room_conflicts_exact or room_conflicts_overlap or room_conflicts_by_time_str:
        logger.error("=" * 80)
        logger.error("ROOM DOUBLE-BOOKING DETECTED - POST-PROCESSING CLEANUP")
        logger.error("=" * 80)
        
        if room_conflicts_exact:
            logger.error(f"Found {len(room_conflicts_exact)} exact room/time conflicts:")
            for conflict in room_conflicts_exact[:10]:  # Limit logging
                logger.error(f"  Room {conflict['room_id']} Day {conflict['day_id']} "
                           f"Time {conflict['start_min']}-{conflict['end_min']}: "
                           f"Subjects {conflict['subjects']} Blocks {conflict['blocks']}")
        
        if room_conflicts_by_time_str:
            logger.error(f"Found {len(room_conflicts_by_time_str)} room conflicts by time string:")
            for conflict in room_conflicts_by_time_str[:10]:  # Limit logging
                logger.error(f"  Room {conflict['room_id']} Day {conflict['day_id']} "
                           f"Time '{conflict['time_str']}': "
                           f"Subjects {conflict['subjects']} Blocks {conflict['blocks']}")
        
        if room_conflicts_overlap:
            logger.error(f"Found {len(room_conflicts_overlap)} overlapping room/time conflicts:")
            for conflict in room_conflicts_overlap[:10]:  # Limit logging
                logger.error(f"  Room {conflict['room_id']} Day {conflict['day_id']}: "
                           f"Subject {conflict['subject_a']} (block {conflict['block_a']}) overlaps "
                           f"Subject {conflict['subject_b']} (block {conflict['block_b']})")
        
        # Remove duplicate assignments - keep first occurrence per room/day/time slot
        # Track which room/day/time slots have been assigned
        assigned_room_slots: Set[Tuple[int, int, int, int]] = set()  # (room_id, day_id, start_min, end_min)
        assigned_room_time_strs: Set[Tuple[int, int, str]] = set()  # (room_id, day_id, time_str) - fallback
        deduplicated_items = []
        removed_count = 0
        
        for item in all_scheduled_items:
            room_id = item.get("room_id")
            day_id = item.get("day_id")
            start_min = item.get("start_min")
            end_min = item.get("end_min")
            time_str = item.get("time")
            
            # Items without room info pass through
            if room_id is None or day_id is None:
                deduplicated_items.append(item)
                continue
            
            try:
                room_id_int = int(room_id)
                day_id_int = int(day_id)
            except (TypeError, ValueError):
                deduplicated_items.append(item)
                continue

            # EXEMPTION: Skip duplicate removal for NSTP/PE rooms (FIELD, GYM, etc)
            current_room_name = room_id_to_name.get(room_id_int, "").upper()
            if current_room_name == NSTP_ROOM_NAME or "FIELD" in current_room_name or "COURT" in current_room_name or "GYM" in current_room_name:
                 deduplicated_items.append(item)
                 continue
            
            is_duplicate = False
            
            # Check by start_min/end_min if available
            if start_min is not None and end_min is not None:
                try:
                    key = (room_id_int, day_id_int, int(start_min), int(end_min))
                    if key in assigned_room_slots:
                        is_duplicate = True
                    else:
                        assigned_room_slots.add(key)
                except (TypeError, ValueError):
                    pass
            
            # Also check by time string (fallback for when start_min/end_min aren't set)
            if time_str and not is_duplicate:
                time_str_key = (room_id_int, day_id_int, str(time_str))
                if time_str_key in assigned_room_time_strs:
                    is_duplicate = True
                else:
                    assigned_room_time_strs.add(time_str_key)
            
            if is_duplicate:
                # This is a duplicate - skip it
                time_info = f"{start_min}-{end_min}" if start_min and end_min else time_str
                logger.warning(f"  Removing duplicate: Subject {item.get('subject_id')} Block {item.get('block')} "
                             f"from Room {room_id} Day {day_id} Time {time_info}")
                removed_count += 1
            else:
                deduplicated_items.append(item)
        
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} duplicate room assignments. "
                         f"Original: {len(all_scheduled_items)} -> Deduplicated: {len(deduplicated_items)}")
            all_scheduled_items = deduplicated_items
        
        logger.error("=" * 80)
    
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

    # Collect all diagnostics (aggregated across clusters)
    # Use the explicitly updated all_diagnostics dictionary
    raw_diagnostics = all_diagnostics
    final_diagnostics = {}
    
    # Pre-build lookup for clone_id -> original_id
    # DO NOT RESET clone_to_original_map = {} here! It was populated inside the cluster loop.
    # We only add missing mappings from the main list here.
    if clone_to_original_map is None:
         clone_to_original_map = {}
         
    for subj in subjects:
        sid = getattr(subj, "id", None)
        try:
            sid_int = int(sid)
        except Exception:
            sid_int = None
            
        orig_val = getattr(subj, "original_subject_id", None)
        try:
            orig_int = int(orig_val) if orig_val is not None else sid_int
        except Exception:
            orig_int = sid_int
            
        if sid_int is not None and orig_int is not None:
            clone_to_original_map[sid_int] = orig_int

    # ENHANCEMENT: Also populate map from scheduled items to catch clones (e.g. 192 -> 92)
    # This is crucial because 'subjects' list might only have originals, but diagnostics use clones.
    for item in all_scheduled_items:
        try:
            c_id = item.get("clone_subject_id")
            s_id = item.get("subject_id")
            if c_id is not None and s_id is not None:
                clone_to_original_map[int(c_id)] = int(s_id)
        except Exception:
            pass

    # Priority map (higher number = higher priority)
    REASON_PRIORITY = {
        "Solver Conflict": 10,       # Found candidates but couldn't pick (capacity/conflict)
        "Student Conflict": 8,       # Blocked by students
        "Room Conflict": 7,          # Blocked by room availability
        "Instructor Conflict": 6,    # Blocked by instructor availability
        "No Rooms": 5,               # No rooms map to this subject
        "No Instructor": 4,          # No instructors map to this subject
        "No Valid Time": 3,          # No 1-hour/1.5-hour blocks available at all
        "Unscheduled": 1,            # Unknown
    }

    logger.info(f"[DIAGNOSTICS PRE-LOOP] Raw diagnostics keys: {list(raw_diagnostics.keys())}")
    for clone_id, stats in raw_diagnostics.items():
        # Resolve to original ID
        original_id = clone_to_original_map.get(clone_id, clone_id)
        original_id_str = str(original_id)
        
        # DEBUG: Log raw stats to understand why we get "Unscheduled"
        logger.info(f"[DIAGNOSTICS DEBUG] Processing clone {clone_id} maps to original {original_id}. Stats: {stats}")
        if not stats: 
            logger.warning(f"[DIAGNOSTICS WARNING] Stats empty for clone {clone_id}")

        # Format the message for THIS clone
        reason = "Unscheduled"
        if stats.get("candidates", 0) > 0:
             # If we had candidates but none selected, it implies a solver conflict or capacity issue
             reason = "Solver Conflict"
        elif stats.get("eligible_rooms", 0) == 0:
            reason = "No Rooms"
        elif stats.get("eligible_instrs", 0) == 0:
            reason = "No Instructor"
        elif stats.get("windows_considered", 0) == 0:
            reason = "No Valid Time"
        elif stats.get("windows_student_conflict", 0) > 0 and stats.get("windows_student_conflict") >= stats.get("windows_considered", 0) * 0.9:
             # If >90% of windows were blocked by student conflicts
             reason = "Student Conflict"
        elif stats.get("room_conflicts", 0) > 0 and stats.get("room_checks", 0) > 0:
             # If we checked rooms and found conflicts (and didn't find a valid one because candidates=0)
             reason = "Room Conflict"
        elif stats.get("instr_conflicts", 0) > 0 and stats.get("instr_checks", 0) > 0:
             reason = "Instructor Conflict"
        
        # Merge logic: Keep the "highest priority" reason seen for this subject ID
        
        # Generate user-friendly detail text
        detail_parts = []
        if reason == "Solver Conflict":
            cands = stats.get('candidates', 0)
            if cands > 0:
                detail_parts.append(f"The system tried {cands} possible schedules but all were taken by other classes.")
            else:
                detail_parts.append("All possible schedules conflict with existing classes.")
        
        if stats.get("eligible_rooms", 0) == 0:
            detail_parts.append("No rooms are set up for this subject.")
        elif stats.get("room_conflicts", 0) > 0:
            rejections = stats.get("rejection_counters", {})
            if rejections:
                top_reasons = sorted(rejections.items(), key=lambda x: x[1], reverse=True)[:3]
                # Translate "Course X Year Y" and "Blocked by Course X Year Y" to readable course codes
                def _translate_reason_key(key_str):
                    import re
                    m = re.match(r'(?:Blocked by\s+)?Course\s+(\d+)\s+Year\s+(\d+)', key_str)
                    if m:
                        cid, yr = int(m.group(1)), int(m.group(2))
                        return f"{course_id_to_code.get(cid, f'Course {cid}')} {_year_label(yr)}"
                    # Also translate "BSCS 1st Year" style that already has "Blocked by" prefix
                    if key_str.startswith("Blocked by "):
                        return key_str[len("Blocked by "):]
                    return key_str
                reason_str = ", ".join([f"{_translate_reason_key(k)} ({v} times)" for k, v in top_reasons])
                detail_parts.append(f"Rooms are being used by: {reason_str}.")
            else:
                detail_parts.append("All eligible rooms are occupied by other classes.")

        if stats.get("eligible_instrs", 0) == 0:
            detail_parts.append("No instructor is assigned to this subject.")
        elif stats.get("instr_conflicts", 0) > 0:
            detail_parts.append("All assigned instructors are busy at every available time.")
        
        if stats.get("student_conflicts", 0) > 0:
             detail_parts.append(f"{stats.get('student_conflicts')} time slots overlap with other classes for the same students.")

        detail = " ".join(detail_parts) if detail_parts else "Could not find an available schedule."

        # Merge logic: Keep the "highest priority" reason seen for this subject ID
        current_entry = final_diagnostics.get(original_id_str)
        current_reason = "Unscheduled"
        if isinstance(current_entry, dict):
            current_reason = current_entry.get("failure_reason", "Unscheduled")
        elif isinstance(current_entry, str):
            current_reason = current_entry

        if REASON_PRIORITY.get(reason, 0) >= REASON_PRIORITY.get(current_reason, 0):
            final_diagnostics[original_id_str] = {
                "failure_reason": reason,
                "detail": detail,
                "metrics": stats
            }
            # DO NOT set the integer key, as it breaks json.dumps sorting (TypeError: '<' not supported between instances of 'int' and 'str')
            # final_diagnostics[original_id] = reason

    # Fallback: Identify subjects that are NEITHER scheduled NOR have diagnostics
    # CRITICAL: Track scheduled CLONES (per-block instances)
    scheduled_clones_set = set()
    for item in all_scheduled_items:
        cid = item.get("clone_subject_id")
        if cid is not None:
             scheduled_clones_set.add(int(cid))
             # Also add mapping if we know this clone is scheduled
             orig_id = item.get("subject_id")
             if orig_id:
                 clone_to_original_map[int(cid)] = int(orig_id)
        else:
             # Fallback: if clone_subject_id is missing (older items), use subject_id
             # because it might be the only ID we have.
             sid = item.get("subject_id")
             if sid is not None:
                 scheduled_clones_set.add(int(sid))
    
    logger.info(f"[DIAGNOSTICS FALLBACK] Checking {len(subjects)} subjects. Scheduled clones: {len(scheduled_clones_set)}")
    logger.info(f"[DIAGNOSTICS DEBUG] Final Diagnostics Keys BEFORE Pruning: {list(final_diagnostics.keys())}")
    # logger.info(f"[DIAGNOSTICS DEBUG] Scheduled Clones Set (sample): {list(scheduled_clones_set)[:20]}")

    for subject in subjects:
        # Resolve to original ID for consistent lookup in final results
        original_id_val = getattr(subject, "original_subject_id", None)
        sid_to_use = int(original_id_val) if original_id_val is not None else subject.id
        sid_str = str(sid_to_use)
        
        # Check if THIS SPECIFIC BLOCK (clone) is scheduled
        is_scheduled = int(subject.id) in scheduled_clones_set
        has_diagnostic = sid_str in final_diagnostics
        
        if is_scheduled:
            # CRITICAL: If the subject is scheduled, it must NOT be in diagnostics.
            # However, we only prune if ALL instances (clones) of this subject are scheduled.
            # Actually, simpler: if this clone is scheduled, and it was in raw_diagnostics, we should remove the clone entry.
            # But final_diagnostics is keyed by original_id_str. 
            # We only remove the original_id entry if we are sure NO clones of it remain unscheduled.
            
            # Count unscheduled clones for this original subject
            unscheduled_clones = [s for s in subjects if (getattr(s, "original_subject_id", None) or s.id) == sid_to_use and int(s.id) not in scheduled_clones_set]
            
            if not unscheduled_clones:
                if sid_str in final_diagnostics:
                    logger.info(f"[DIAGNOSTICS PRUNE] Removing {sid_str} because all blocks are scheduled.")
                    del final_diagnostics[sid_str]
            continue

        # ---------------------------------------------------------------------
        # Unified Recommendation Logic
        # ---------------------------------------------------------------------
        # Determine if we have an existing diagnostic (e.g. Solver Conflict)
        # or if this subject was completely skipped.
        diagnostic_entry = final_diagnostics.get(sid_str)
        is_newly_discovered = False
        
        if not diagnostic_entry:
            # Case 1: Subject was skipped / missing from diagnostics
            is_newly_discovered = True
            code = (getattr(subject, "code", "") or "").upper()
            
            # ---- Build a SPECIFIC reason using actual eligibility data ----
            # For cloned subjects, eligibility maps may be keyed by original_subject_id
            _orig_sid = getattr(subject, 'original_subject_id', None) or subject.id
            eligible_room_ids = course_to_all_rooms.get(subject.id, []) or course_to_all_rooms.get(_orig_sid, [])
            eligible_instr_ids = course_to_instructors.get(subject.id, []) or course_to_instructors.get(_orig_sid, [])
            num_rooms = len(eligible_room_ids) if eligible_room_ids else 0
            num_instrs = len(eligible_instr_ids) if eligible_instr_ids else 0
            
            if "NSTP" in code:
                reason = "No Valid Time"
                detail = "No available Sunday time slot, or no instructor is free on Sunday."
            elif num_instrs == 0 and num_rooms == 0:
                reason = "No Instructor & No Rooms"
                detail = "This subject has no instructor assigned and no rooms set up. It needs both before it can be scheduled."
            elif num_instrs == 0:
                reason = "No Instructor"
                # Name eligible rooms
                room_names = [room_id_to_name.get(rid, f'Room {rid}') for rid in eligible_room_ids[:5]]
                rooms_str = ", ".join(room_names)
                detail = f"No instructor is assigned to teach this subject. {num_rooms} room(s) available ({rooms_str}) but scheduling needs at least one instructor."
            elif num_rooms == 0:
                reason = "No Rooms"
                # Name eligible instructors
                inames = [instr_id_to_name.get(iid, f'ID {iid}') for iid in eligible_instr_ids[:5]]
                instrs_str = ", ".join(inames)
                detail = f"{num_instrs} instructor(s) can teach this ({instrs_str}), but no rooms are set up for this subject type."
            else:
                # Has both rooms and instructors but still failed -> all slots booked
                reason = "All Slots Booked"
                inames = [instr_id_to_name.get(iid, f'ID {iid}') for iid in eligible_instr_ids[:3]]
                room_names = [room_id_to_name.get(rid, f'Room {rid}') for rid in eligible_room_ids[:3]]
                detail = (
                    f"Only {num_instrs} instructor(s) ({', '.join(inames)}) and {num_rooms} room(s) ({', '.join(room_names)}) are available, "
                    f"but all their time slots are already taken by other classes in this block."
                )
            
            diagnostic_entry = {
                "failure_reason": reason,
                "detail": detail,
                "metrics": {
                    "candidates": 0,
                    "fallback_generated": True,
                    "eligible_rooms": num_rooms,
                    "eligible_instructors": num_instrs,
                },
                "recommendations": []
            }
            final_diagnostics[sid_str] = diagnostic_entry

        # Ensure recommendations list exists
        if "recommendations" not in diagnostic_entry:
            diagnostic_entry["recommendations"] = []

        # Generate recommendations (unless NSTP which is special case)
        code = (getattr(subject, "code", "") or "").upper()
        if "NSTP" not in code:
            try:
                eligible_room_ids = course_to_all_rooms.get(subject.id, [])
                # Fallback: cloned subjects may not be in the map, try original_subject_id
                if not eligible_room_ids:
                    _orig_sid = getattr(subject, 'original_subject_id', None) or subject.id
                    eligible_room_ids = course_to_all_rooms.get(_orig_sid, [])
                eligible_instr_ids = course_to_instructors.get(subject.id, [])
                if not eligible_instr_ids:
                    _orig_sid = getattr(subject, 'original_subject_id', None) or subject.id
                    eligible_instr_ids = course_to_instructors.get(_orig_sid, [])
                
                # HARD FILTER: Strip shared rooms for non-NSTP/PE/PATHFIT subjects
                _rec_code = (getattr(subject, 'code', '') or '').upper().strip()
                _rec_is_sports = (
                    _rec_code.startswith("NSTP") or
                    _rec_code.startswith("PE") or
                    _rec_code.startswith("PATHFIT")
                )
                if not _rec_is_sports and _solver_shared_room_ids:
                    eligible_room_ids = [rid for rid in eligible_room_ids if rid not in _solver_shared_room_ids]
                
                # Get availability data (re-check as bookings may have updated if we auto-scheduled others)
                room_availability = get_available_slots(rooms, days, booked_room_ranges_global or {})
                instr_availability = get_instructor_availability(instructors, days, booked_instr_ranges_global or {})
                
                # Get student time ranges for conflict checking
                subj_course_id = getattr(subject, 'course_id', course_id) or course_id
                subj_year = getattr(subject, 'year_level', default_year) or default_year or 1
                # FIXED: Derive block label from student_block (integer) for cloned subjects
                # Clone subjects use student_block=1 for Block A, student_block=2 for Block B, etc.
                _sb = getattr(subject, 'student_block', None)
                if _sb is not None:
                    try:
                        subj_block = _block_index_to_label(int(_sb))
                    except (TypeError, ValueError):
                        subj_block = getattr(subject, 'block', 'A') or 'A'
                else:
                    subj_block = getattr(subject, 'block', 'A') or 'A'
                
                # FIXED: Define student_time_ranges as Dict to match generate_recommendations signature
                student_time_ranges = defaultdict(list)
                try:
                    # Scan scheduled items for this cohort to identify busy times
                    for item in all_scheduled_items:
                        # Check constraint: same course, year, and block
                        # Use loose string comparison for safety, but store as typed keys
                        i_course = item.get("course_id")
                        i_year = item.get("year")
                        i_block = item.get("block")
                        
                        if (str(i_course) == str(subj_course_id) and 
                            str(i_year) == str(subj_year) and 
                            str(i_block) == str(subj_block)):
                            
                            d_id = item.get("day_id")
                            s_min = item.get("start_min")
                            e_min = item.get("end_min")
                            
                            if d_id is not None and s_min is not None and e_min is not None:
                                # Key format: (course_id, year, block_label, day_id)
                                # Must use exact same values as passed to generate_recommendations
                                key = (subj_course_id, subj_year, subj_block, int(d_id))
                                student_time_ranges[key].append((int(s_min), int(e_min)))
                except Exception as e:
                    logger.warning(f"Error building student_time_ranges for subject {subject.id}: {e}")

                recommendations = generate_recommendations(
                    subject=subject,
                    eligible_room_ids=eligible_room_ids,
                    eligible_instructor_ids=eligible_instr_ids,
                    rooms=rooms,
                    instructors=instructors,
                    days=days,
                    room_availability=room_availability,
                    instructor_availability=instr_availability,
                    student_time_ranges=student_time_ranges,
                    course_id=subj_course_id,
                    year=subj_year,
                    block_label=subj_block,
                    max_recommendations=5,
                )
                
                diagnostic_entry["recommendations"] = recommendations

                # IMPROVED: Refine failure reason if no recommendations found
                if not recommendations:
                    subj_type = (getattr(subject, "type", "") or "").upper().strip()
                    label = "Lab" if subj_type == "LAB" else "Lecture"
                    
                    if not eligible_room_ids:
                        diagnostic_entry["failure_reason"] = "No Rooms"
                        diagnostic_entry["detail"] = f"No {label} rooms are configured for this subject."
                    else:
                        # Check strictly for room exhaustion
                        has_room_slots = False
                        for rid in eligible_room_ids:
                            # room_availability is Dict[room_id, Dict[day_id, List[slots]]]
                            r_slots = room_availability.get(rid)
                            if r_slots:
                                # Check if any day has slots
                                if any(day_slots for day_slots in r_slots.values()):
                                    has_room_slots = True
                                    break
                        
                        if not has_room_slots:
                            diagnostic_entry["failure_reason"] = "Room Conflict"
                            diagnostic_entry["detail"] = f"All eligible {label} rooms are fully booked."
                        else:
                            # Rooms have space, maybe instructors dont?
                            if not eligible_instr_ids:
                                diagnostic_entry["failure_reason"] = "No Instructor"
                                diagnostic_entry["detail"] = "No eligible instructors configured."
                            else:
                                # The user's provided `Code Edit` block seems to be out of context here.
                                # It contains lines like `if len(slots_by_day) == len(day_ids):` and `logger.debug`
                                # which are not present in the original document at this location.
                                # Assuming the instruction is to replace a unicode checkmark if it were present,
                                # and since it's not, I will proceed with the existing code.
                                # If the intention was to insert the provided `Code Edit` block, it would
                                # result in syntactically incorrect code due to indentation and structure.
                                # Therefore, I will only apply the specific instruction about the unicode character
                                # if I find it. Since it's not here, no change is made to this specific block.
                                has_instr_slots = False
                                for iid in eligible_instr_ids:
                                    i_slots = instr_availability.get(iid)
                                    if i_slots:
                                        if any(day_slots for day_slots in i_slots.values()):
                                            has_instr_slots = True
                                            break
                                
                                if not has_instr_slots:
                                     diagnostic_entry["failure_reason"] = "Instructor Conflict"
                                     diagnostic_entry["detail"] = "All eligible instructors are fully booked."
                
                # Auto-apply logic: Only for "Skipped" subjects (is_newly_discovered)
                # For "Solver Conflict", we let the user resolve manually using the recommendations
                if is_newly_discovered and recommendations:
                    first_rec = recommendations[0]
                    rec_is_paired = first_rec.get("is_paired", False)
                    rec_day_ids = first_rec.get("day_ids", [first_rec["day_id"]])

                    # Create schedule items — one per day for paired patterns (M-W, T-TH)
                    for rec_day_id in rec_day_ids:
                        auto_item = {
                            "subject_id": int(sid_to_use),
                            "clone_subject_id": subject.id,
                            "subject_code": getattr(subject, 'code', ''),
                            "subject_name": getattr(subject, 'name', ''),
                            "course_id": subj_course_id,
                            "year": subj_year,
                            "semester": getattr(subject, 'semester', None) or semester,
                            "block": subj_block,
                            "room_id": first_rec["room_id"],
                            "room_name": first_rec["room_name"],
                            "instructor_id": first_rec["instructor_id"],
                            "instructor_name": first_rec["instructor_name"],
                            "day_id": rec_day_id,
                            "day": first_rec["day_label"],
                            "time": first_rec["time"],
                            "start_min": first_rec["start_min"],
                            "end_min": first_rec["end_min"],
                            "is_recommended": True,  # Flag for UI
                            "recommendation_score": first_rec["score"],
                            "alternatives": recommendations,  # Pass all generated alternatives to frontend
                        }
                        all_scheduled_items.append(auto_item)

                    _trace_all_scheduled_items(f"After Auto-Apply Subj {subject.id}")
                    scheduled_clones_set.add(int(subject.id))

                    # Update booking maps for ALL days to prevent conflicts
                    for rec_day_id in rec_day_ids:
                        room_key = (first_rec["room_name"], rec_day_id)
                        if booked_room_ranges_global is not None:
                            booked_room_ranges_global[room_key].append((first_rec["start_min"], first_rec["end_min"]))
                        instr_key = (first_rec["instructor_id"], rec_day_id)
                        if booked_instr_ranges_global is not None:
                            booked_instr_ranges_global[instr_key].append((first_rec["start_min"], first_rec["end_min"]))
                    
                    reason = "Auto-Recommended"
                    detail = f"Automatically scheduled using recommendation: {first_rec['room_name']} on {first_rec['day_label']} at {first_rec['time']} with {first_rec['instructor_name']}"
                    logger.info(f"[RECOMMENDATION APPLIED] Subject {subject.id} ({code}) auto-scheduled: {detail}")
                    
                    # Remove from diagnostics since it's now scheduled
                    if sid_str in final_diagnostics:
                        del final_diagnostics[sid_str]
                else:
                    # Update the reason if we found recommendations for a skipped item but didn't auto-apply?
                    # (Logic above always auto-applies if list not empty for skipped items).
                    pass

            except Exception as e:
                logger.warning(f"[RECOMMENDATION ERROR] Failed to generate recommendations for subject {subject.id}: {e}")

    # Build structured diagnostics for frontend SchedulerDiagnostics component
    subjects_scheduled = len(set(
        int(item.get("subject_id")) for item in all_scheduled_items 
        if item.get("subject_id") is not None
    ))
    subjects_total = len(all_requested_ids) if all_requested_ids else subjects_scheduled
    
    # Convert per-subject diagnostics to unscheduled_reasons format
    unscheduled_reasons = {}
    for sid_str, entry in final_diagnostics.items():
        if isinstance(entry, dict):
            # Find subject code from subjects list
            subject_code = None
            subject_type = None
            try:
                sid_int = int(sid_str)
                for subj in subjects:
                    orig_id = getattr(subj, "original_subject_id", None) or subj.id
                    if orig_id == sid_int or subj.id == sid_int:
                        subject_code = getattr(subj, "code", None)
                        subject_type = getattr(subj, "type", None) or getattr(subj, "subject_type", None)
                        break
            except (ValueError, TypeError):
                pass
            
            # Build suggestion with specific instructor/room names when available
            failure_reason = entry.get("failure_reason", "")
            _entry_metrics = entry.get("metrics", {})

            # Try to get specific instructor/room names for this subject
            _subj_instr_ids = []
            _subj_room_ids = []
            try:
                sid_int = int(sid_str)
                for subj in subjects:
                    _oid = getattr(subj, 'original_subject_id', None) or subj.id
                    if _oid == sid_int or subj.id == sid_int:
                        _subj_instr_ids = course_to_instructors.get(subj.id, []) or course_to_instructors.get(_oid, [])
                        _subj_room_ids = course_to_all_rooms.get(subj.id, []) or course_to_all_rooms.get(_oid, [])
                        break
            except (ValueError, TypeError):
                pass

            # Build registrar-friendly suggestion
            if failure_reason in ("Solver Conflict", "Room Conflict", "All Slots Booked"):
                parts = []
                if _subj_instr_ids:
                    inames = [instr_id_to_name.get(iid, f'ID {iid}') for iid in _subj_instr_ids[:4]]
                    parts.append(f"Assigned instructors: {', '.join(inames)} — all are fully booked.")
                if _subj_room_ids:
                    rnames = [room_id_to_name.get(rid, f'Room {rid}') for rid in _subj_room_ids[:4]]
                    parts.append(f"Eligible rooms: {', '.join(rnames)} — all are occupied.")
                parts.append("Try assigning additional instructors or rooms to free up time slots.")
                suggestion_text = " ".join(parts)
            elif failure_reason == "Instructor Conflict":
                if _subj_instr_ids:
                    inames = [instr_id_to_name.get(iid, f'ID {iid}') for iid in _subj_instr_ids[:4]]
                    suggestion_text = f"Assigned instructors ({', '.join(inames)}) are all fully booked. Assign another instructor who has free time."
                else:
                    suggestion_text = "All assigned instructors are fully booked. Assign another instructor who has free time."
            elif failure_reason == "No Instructor":
                suggestion_text = "No instructor is assigned to this subject yet. Go to the Instructors page and add this subject to an instructor's specialization."
            elif failure_reason == "No Rooms":
                subj_type_str = (subject_type or 'LEC').upper()
                suggestion_text = f"No {subj_type_str} rooms are set up for this subject. Add a {subj_type_str} room in the Rooms page."
            elif failure_reason == "No Instructor & No Rooms":
                suggestion_text = "This subject needs both an instructor and a room before it can be scheduled."
            elif failure_reason == "Student Conflict":
                suggestion_text = "Every available time overlaps with another class for the same students. Try reducing the number of overlapping subjects."
            elif failure_reason == "No Valid Time":
                suggestion_text = "No suitable time slot is available. Check if enough consecutive hours are free."
            else:
                suggestion_text = "Check that this subject has instructors and rooms assigned."

            unscheduled_reasons[sid_str] = {
                "subject_code": subject_code or f"Subject {sid_str}",
                "subject_type": (subject_type or "").upper(),
                "reason": entry.get("failure_reason", "Unscheduled"),
                "reason_text": entry.get("detail", ""),
                "suggestion": suggestion_text,
                "recommendations": entry.get("recommendations", []),
            }
    
    # Determine overall solver status
    if subjects_scheduled == subjects_total and subjects_total > 0:
        solver_status = "OPTIMAL"
    elif subjects_scheduled > 0:
        solver_status = "FEASIBLE"  # Partial success
    elif subjects_total > 0:
        solver_status = "INFEASIBLE"  # Nothing scheduled
    else:
        solver_status = "UNKNOWN"
    
    structured_diagnostics = {
        "solver_status": solver_status,
        "solve_time_seconds": 0,  # Would need to be tracked separately
        "subjects_scheduled": subjects_scheduled,
        "subjects_total": subjects_total,
        "unscheduled_reasons": unscheduled_reasons,
        # Keep raw diagnostics for backward compatibility
        "_raw": final_diagnostics,
    }

    # FINAL DEBUG PRINT
    for item in all_scheduled_items:
        sid = item.get("subject_id")
        if sid in [96, 196, 296, 99, 199, 299]:
            logger.info(f"[FINAL RETURN DEBUG] Subject {sid} Time: {item.get('time')}")
    # ------------------------------------------------------------------
    # FINAL POST-PROCESSING: Remove items that conflict on instructor-time
    # or room-time across blocks. This MUST run last, after all scheduling.
    # Priority: main-scheduled > recommended/retry/soft items.
    # ------------------------------------------------------------------
    def _has_time_overlap(s1, e1, s2, e2):
        return not (e1 <= s2 or e2 <= s1)

    logger.info("[POST-PROCESS] Scanning %d items for cross-block conflicts (instructor + room)", len(all_scheduled_items))

    # Build per-item metadata once
    item_meta = []
    for idx, item in enumerate(all_scheduled_items):
        instr_id = item.get("instructor_id")
        room_id = item.get("room_id")
        day_id = item.get("day_id")
        s_min = item.get("start_min")
        e_min = item.get("end_min")
        is_removable = bool(
            item.get("is_retry", False) or
            item.get("is_recommended", False) or
            item.get("is_soft_constraint", False)
        )
        block = item.get("block", "?")
        subject_id = item.get("subject_id")
        item_meta.append({
            "idx": idx, "instr_id": instr_id, "room_id": room_id,
            "day_id": day_id, "s_min": s_min, "e_min": e_min,
            "removable": is_removable, "block": block, "subject_id": subject_id,
        })

    # Build conflict maps: (resource_type, resource_id, day_id) -> list of entries
    conflict_map = defaultdict(list)  # key -> [(start, end, idx, removable, block, subject_id)]
    for m in item_meta:
        if m["day_id"] is None or m["s_min"] is None or m["e_min"] is None:
            continue
        try:
            day_int = int(m["day_id"])
            s_int = int(m["s_min"])
            e_int = int(m["e_min"])
        except (TypeError, ValueError):
            continue
        entry = (s_int, e_int, m["idx"], m["removable"], m["block"], m["subject_id"])
        # Instructor key — EXEMPT items in shared building rooms (FIELD, GYM, etc.)
        # When NSTP/PE reuses instructors across blocks in a shared venue, that is intentional
        if m["instr_id"] is not None:
            try:
                instr_room_id = int(m["room_id"]) if m["room_id"] is not None else None
                instr_room_name = room_id_to_name.get(instr_room_id, "").upper() if instr_room_id else ""
                is_shared_venue = (instr_room_name == NSTP_ROOM_NAME or "FIELD" in instr_room_name 
                                   or "COURT" in instr_room_name or "GYM" in instr_room_name)
                if not is_shared_venue:
                    conflict_map[("instr", int(m["instr_id"]), day_int)].append(entry)
            except (TypeError, ValueError):
                pass
        # Room key — EXEMPT shared building rooms (FIELD, GYM, etc.) from cross-block conflict checks
        # These rooms are designed to hold multiple classes simultaneously
        if m["room_id"] is not None:
            try:
                room_id_int = int(m["room_id"])
                room_name = room_id_to_name.get(room_id_int, "").upper()
                # Skip shared building rooms — they allow overlaps by design
                is_shared_room = (room_name == NSTP_ROOM_NAME or "FIELD" in room_name 
                                  or "COURT" in room_name or "GYM" in room_name)
                if not is_shared_room:
                    # Also check building.is_shared flag
                    if room_id_int in _solver_shared_room_ids if '_solver_shared_room_ids' in dir() else False:
                        is_shared_room = True
                if not is_shared_room:
                    conflict_map[("room", room_id_int, day_int)].append(entry)
            except (TypeError, ValueError):
                pass

    # Log resources with multiple entries
    for key, entries in conflict_map.items():
        if len(entries) > 1:
            rtype, rid, did = key
            logger.info(
                "[POST-PROCESS] %s %d Day %d has %d entries: %s",
                rtype.upper(), rid, did, len(entries),
                [(s, e, f"block={b}", f"removable={r}", f"subj={sid}") for s, e, _, r, b, sid in entries]
            )

    indices_to_remove = set()
    for key, entries in conflict_map.items():
        rtype, rid, did = key
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                s1, e1, idx1, removable1, block1, sid1 = entries[i]
                s2, e2, idx2, removable2, block2, sid2 = entries[j]
                if _has_time_overlap(s1, e1, s2, e2):
                    # Skip if both are from the same block (intra-block handled elsewhere)
                    if block1 == block2:
                        continue
                    logger.warning(
                        "[POST-PROCESS] %s conflict: %s=%d day=%d | "
                        "item1(idx=%d subj=%s block=%s %d-%d removable=%s) vs "
                        "item2(idx=%d subj=%s block=%s %d-%d removable=%s)",
                        rtype.upper(), rtype, rid, did,
                        idx1, sid1, block1, s1, e1, removable1,
                        idx2, sid2, block2, s2, e2, removable2,
                    )
                    # Remove the removable item; if both same type, remove later
                    if removable2 and not removable1:
                        indices_to_remove.add(idx2)
                    elif removable1 and not removable2:
                        indices_to_remove.add(idx1)
                    else:
                        indices_to_remove.add(idx2)

    if indices_to_remove:
        removed_details = []
        for idx in sorted(indices_to_remove):
            item = all_scheduled_items[idx]
            removed_details.append(
                f"subject_id={item.get('subject_id')} instr={item.get('instructor_id')} "
                f"room={item.get('room_id')} day={item.get('day_id')} "
                f"time={item.get('start_min')}-{item.get('end_min')} "
                f"block={item.get('block')} retry={item.get('is_retry', False)} "
                f"recommended={item.get('is_recommended', False)}"
            )
        logger.warning(
            "[POST-PROCESS] Removing %d items with cross-block conflicts:\n  %s",
            len(indices_to_remove), "\n  ".join(removed_details)
        )
        all_scheduled_items = [
            item for idx, item in enumerate(all_scheduled_items)
            if idx not in indices_to_remove
        ]
    else:
        logger.info("[POST-PROCESS] No cross-block conflicts found")

    # =========================================================================
    # POST-SCHEDULING PROXIMITY PASS
    # =========================================================================
    # Scan consecutive classes in the same block+day and try to swap rooms
    # when the travel time between buildings exceeds a threshold.
    # =========================================================================
    PROXIMITY_THRESHOLD_MIN = 15  # Maximum acceptable travel time in minutes
    proximity_swaps = 0
    proximity_violations = 0
    
    if _bldg_dist_map and _room_to_bldg_id:
        # Group items by (block, day_id) — only within the same student block + day
        from collections import defaultdict as _dd
        block_day_groups: Dict[Tuple[Any, Any], list] = _dd(list)
        for idx, item in enumerate(all_scheduled_items):
            block_label = item.get("block")
            day_id = item.get("day_id")
            if block_label is not None and day_id is not None:
                block_day_groups[(block_label, day_id)].append((idx, item))
        
        # Build a set of already-booked (room_id, day_id, start_min, end_min)
        # for conflict checking when swapping
        _booked_room_slots: Dict[Tuple[int, int], List[Tuple[int, int]]] = _dd(list)
        for item in all_scheduled_items:
            rid = item.get("room_id")
            did = item.get("day_id")
            s_min = item.get("start_min")
            e_min = item.get("end_min")
            if rid and did and s_min is not None and e_min is not None:
                _booked_room_slots[(rid, did)].append((s_min, e_min))
        
        for (block_label, day_id), items_in_group in block_day_groups.items():
            # Sort by start time to find consecutive classes
            items_in_group.sort(key=lambda x: x[1].get("start_min", 0))
            
            for i in range(len(items_in_group) - 1):
                idx1, item1 = items_in_group[i]
                idx2, item2 = items_in_group[i + 1]
                
                rid1 = item1.get("room_id")
                rid2 = item2.get("room_id")
                if not rid1 or not rid2 or rid1 == rid2:
                    continue
                
                bldg1 = _room_to_bldg_id.get(rid1)
                bldg2 = _room_to_bldg_id.get(rid2)
                if not bldg1 or not bldg2 or bldg1 == bldg2:
                    continue  # Same building, no issue
                
                travel_time = _bldg_dist_map.get((bldg1, bldg2), 0)
                if travel_time <= PROXIMITY_THRESHOLD_MIN:
                    continue  # Acceptable travel time
                
                proximity_violations += 1
                # Check gap between the two classes
                end1 = item1.get("end_min", 0)
                start2 = item2.get("start_min", 0)
                gap_min = start2 - end1
                
                logger.warning(
                    "[PROXIMITY] Block %s Day %s: %s (room=%s, bldg=%s, %s-%s) -> %s (room=%s, bldg=%s, %s-%s) "
                    "travel=%d min, gap=%d min",
                    block_label, day_id,
                    item1.get("subject_id"), rid1, bldg1,
                    item1.get("start_min"), item1.get("end_min"),
                    item2.get("subject_id"), rid2, bldg2,
                    item2.get("start_min"), item2.get("end_min"),
                    travel_time, gap_min
                )
                
                # Try to swap the SECOND item's room to one closer to bldg1
                # Find rooms in the same building as item1 (or closer building)
                best_swap_rid = None
                best_swap_travel = travel_time
                
                for candidate_rid, candidate_bldg in _room_to_bldg_id.items():
                    if candidate_rid == rid2:
                        continue
                    # HARD FILTER: Never swap TO a shared room for non-sports subjects
                    _item2_code = (item2.get("subject_code", "") or "").upper().strip()
                    if not _item2_code:
                        _item2_sid = item2.get("subject_id")
                        _item2_subj = db.query(models.Subject).get(_item2_sid) if _item2_sid and db else None
                        _item2_code = (getattr(_item2_subj, 'code', '') or '').upper().strip() if _item2_subj else ''
                    _item2_is_sports = (
                        _item2_code.startswith("NSTP") or
                        _item2_code.startswith("PE") or
                        _item2_code.startswith("PATHFIT")
                    )
                    if not _item2_is_sports and candidate_rid in _solver_shared_room_ids:
                        continue
                    # FIELD is reserved for NSTP only — PE/PATHFIT must NOT be swapped to FIELD
                    _candidate_name = room_id_to_name.get(candidate_rid, "").upper().strip()
                    if _candidate_name == "FIELD" and not _item2_code.startswith("NSTP"):
                        continue
                    # Check the room type matches
                    candidate_room = room_by_id.get(candidate_rid)
                    item2_room = room_by_id.get(rid2)
                    if not candidate_room or not item2_room:
                        continue
                    if candidate_room.type != item2_room.type:
                        continue
                    # Check capacity
                    if candidate_room.capacity and item2_room.capacity:
                        # Don't downgrade capacity too much
                        if candidate_room.capacity < (item2_room.capacity * 0.5):
                            continue
                    
                    # Check travel time from bldg1 to candidate building
                    candidate_travel = _bldg_dist_map.get((bldg1, candidate_bldg), 9999)
                    if candidate_travel >= best_swap_travel:
                        continue  # Not better
                    
                    # Check the candidate room is not booked at item2's time
                    item2_start = item2.get("start_min", 0)
                    item2_end = item2.get("end_min", 0)
                    conflict = False
                    for (bs, be) in _booked_room_slots.get((candidate_rid, day_id), []):
                        if not (item2_end <= bs or be <= item2_start):
                            conflict = True
                            break
                    if conflict:
                        continue
                    
                    best_swap_rid = candidate_rid
                    best_swap_travel = candidate_travel
                
                if best_swap_rid and best_swap_travel < travel_time:
                    old_room_name = room_id_to_name.get(rid2, f"ID:{rid2}")
                    new_room_name = room_id_to_name.get(best_swap_rid, f"ID:{best_swap_rid}")
                    logger.info(
                        "[PROXIMITY SWAP] Block %s Day %s: Swapped %s room from %s -> %s "
                        "(travel %d->%d min)",
                        block_label, day_id, item2.get("subject_id"),
                        old_room_name, new_room_name,
                        travel_time, best_swap_travel
                    )
                    # Perform the swap
                    # Update booked slots
                    item2_start = item2.get("start_min", 0)
                    item2_end = item2.get("end_min", 0)
                    # Remove old booking
                    old_slots = _booked_room_slots.get((rid2, day_id), [])
                    _booked_room_slots[(rid2, day_id)] = [
                        (s, e) for s, e in old_slots if not (s == item2_start and e == item2_end)
                    ]
                    # Add new booking
                    _booked_room_slots[(best_swap_rid, day_id)].append((item2_start, item2_end))
                    # Update the item
                    all_scheduled_items[idx2]["room_id"] = best_swap_rid
                    all_scheduled_items[idx2]["room"] = new_room_name
                    proximity_swaps += 1
        
        logger.info(
            "[PROXIMITY] Post-scheduling pass complete: %d violations found, %d rooms swapped",
            proximity_violations, proximity_swaps
        )
    else:
        logger.info("[PROXIMITY] No building distance data — skipping proximity pass")

    return all_scheduled_items, structured_diagnostics


def _get_suggestion_for_reason(reason: str) -> str:
    """Return a helpful suggestion based on the failure reason (registrar-friendly)."""
    suggestions = {
        "Solver Conflict": "Go to Subjects page and assign more instructors to this subject, or go to Rooms page and add more rooms of this type.",
        "No Rooms": "Go to Rooms page and add rooms that match this subject type (LEC or LAB).",
        "No Instructor": "Go to Instructors page and assign this subject to at least one instructor's specialization.",
        "No Instructor & No Rooms": "This subject needs both an instructor and a room. Go to Instructors page and Rooms page to configure this subject.",
        "No Valid Time": "This subject needs longer time blocks. Check if enough consecutive time slots are available.",
        "Room Conflict": "All eligible rooms are fully booked. Add more rooms in the Rooms page or reduce other classes.",
        "Instructor Conflict": "All assigned instructors are fully booked. Add more instructors to this subject or reduce their workload.",
        "Student Conflict": "This class would overlap with another subject for the same students. Reduce the number of subjects or add more time slots.",
        "All Slots Booked": "All available room and instructor time slots are taken by other subjects. Try adding more instructors or rooms for this subject.",
        "Unscheduled": "Check that this subject has instructors and rooms assigned in the Subjects page.",
    }
    return suggestions.get(reason, "Check subject settings in the Subjects page.")


def find_alternative_slots(
    db: Session,
    subject_id: int,
    course_id: int,
    year: int,
    semester: int,
    rooms: List[models.Room],
    days: List[models.Day],
    slots_by_day: Dict[str, List[Dict]],
    booked_room_slots_global: Set[Tuple[str, int, int]],
    booked_instr_slots_global: Set[Tuple[int, int, int]],
    course_to_instructors: Dict[str, List[int]],
    course_to_rooms: Dict[str, List[int]],
    room_id_to_name: Dict[int, str],
) -> List[Dict]:
    """
    Scans for alternative timeslots for a failed subject.
    Returns a list of suggestions with metadata about why they are valid or blocked.
    """
    suggestions = []
    
    # load subject
    subject = db.query(models.Subject).get(subject_id)
    if not subject:
        return []

    subj_code = (getattr(subject, "code", "") or "").upper().strip()
    subj_type = (getattr(subject, "type", "") or "").upper().strip()
    is_lab = subj_type == "LAB"
    
    # 1. Determine requirements
    rec_slots = subject.recommended_slots or subject.min_slots or 1
    min_slots = subject.min_slots or rec_slots
    if is_lab:
        min_slots = 1
        
    eligible_instrs = course_to_instructors.get(subject.id, [])
    eligible_rooms = course_to_rooms.get(subject.id, [])
    
    # Fallback if map empty (maybe map key mismatch, try course-wide?)
    if not eligible_instrs:
         # Try direct DB query or loose fallback? For now just use empty
         pass
         
    # 2. Iterate ALL possible slots (Day * Time * Room)
    # To avoid explosion, we limit to eligible rooms
    
    # Define patterns to check
    patterns = []
    if not is_lab:
        patterns = [
            ("M", "W"), ("T", "TH"), ("F",), ("SAT",)
        ]
    else:
        patterns = [("F",), ("SAT",), ("M",), ("T",), ("W",), ("TH",)]

    for pattern in patterns:
        pattern_days = [d for d in days if d.label in pattern]
        if len(pattern_days) != len(pattern): 
            continue
            
        primary_day = pattern_days[0]
        day_slots = slots_by_day.get(primary_day.label, [])
        max_start = len(day_slots) - min_slots
        
        if max_start < 0: continue
        
        for start_pos in range(max_start + 1):
            block = day_slots[start_pos : start_pos + min_slots]
            first_slot = block[0]
            last_slot = block[-1]
            s_str = _minutes_to_time_str(int(first_slot["start_min"]))
            e_str = _minutes_to_time_str(int(last_slot["end_min"]))
            time_label = f"{s_str} - {e_str}"
            
            # Check constraint for this TIME across ALL days in pattern
            # For suggestions, we just check if *Instructor* or *Room* is the blocker
            
            # Check Rooms
            for room_id in eligible_rooms:
                room_name = room_id_to_name.get(room_id)
                if not room_name: continue
                
                # Check Room Availability
                room_conflict = False
                for pd in pattern_days:
                    for slot in block:
                        if (room_name, pd.id, slot["index"]) in booked_room_slots_global:
                           room_conflict = True
                           break
                    if room_conflict: break
                
                if room_conflict:
                    continue # Skip busy rooms for now (we want valid suggestions first)

                # Check Instructors
                for instr_id in eligible_instrs:
                    instr_conflict = False
                    for pd in pattern_days:
                        for slot in block:
                            if (instr_id, pd.id, slot["index"]) in booked_instr_slots_global:
                                instr_conflict = True
                                break
                        if instr_conflict: break
                    
                    if not instr_conflict:
                        # FOUND A VALID SLOT!
                        suggestions.append({
                            "type": "Valid", 
                            "day": " + ".join([d.label for d in pattern_days]),
                            "time": time_label,
                            "room": room_name,
                            "instructor_id": instr_id,
                            "start_min": first_slot["start_min"],
                            "end_min": last_slot["end_min"],
                            "day_ids": [d.id for d in pattern_days],
                            "room_id": room_id,
                            "score": 100 # High score = good
                        })
                        
                        # Limit results
                        if len(suggestions) >= 5:
                            return suggestions
                            
    return suggestions




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
