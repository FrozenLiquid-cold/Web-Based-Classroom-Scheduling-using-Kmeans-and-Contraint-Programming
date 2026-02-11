#!/usr/bin/env python3
"""Test script to trigger scheduling and check results"""

import requests
import json
import time
import os

# API base URL
BASE_URL = os.getenv("SCHEDULER_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _as_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _item_label(item):
    block = item.get("block")
    course_id = item.get("course_id")
    year = item.get("year")
    subject_id = item.get("subject_id")
    clone_subject_id = item.get("clone_subject_id")
    day_id = item.get("day_id")
    start_min = item.get("start_min")
    end_min = item.get("end_min")
    room_id = item.get("room_id")
    instructor_id = item.get("instructor_id")
    time_str = item.get("time")
    return (
        f"block={block} course={course_id} year={year} subj={subject_id} clone={clone_subject_id} "
        f"day={day_id} {start_min}-{end_min} room={room_id} instr={instructor_id} time={time_str}"
    )


def _collect_overlaps(items, key_fn, max_conflicts=50):
    groups = {}
    for item in items:
        day_id = _as_int(item.get("day_id"))
        start_min = _as_int(item.get("start_min"))
        end_min = _as_int(item.get("end_min"))
        if day_id is None or start_min is None or end_min is None:
            continue
        key = key_fn(item)
        if key is None:
            continue
        groups.setdefault(key, []).append((start_min, end_min, item))

    conflicts = []
    for key, intervals in groups.items():
        if len(intervals) < 2:
            continue
        intervals.sort(key=lambda t: (t[0], t[1]))
        active_start, active_end, active_item = intervals[0]
        for start_min, end_min, item in intervals[1:]:
            if start_min < active_end and active_start < end_min:
                conflicts.append((key, active_item, item))
                if len(conflicts) >= max_conflicts:
                    return conflicts
                if end_min > active_end:
                    active_start, active_end, active_item = start_min, end_min, item
            else:
                active_start, active_end, active_item = start_min, end_min, item
    return conflicts

def test_schedule():
    """Trigger a schedule request and monitor progress"""
    
    # Schedule request payload
    course_id = _as_int(os.getenv("SCHEDULE_COURSE_ID")) or 3
    year = _as_int(os.getenv("SCHEDULE_YEAR"))
    if year is None:
        year = 1
    semester = _as_int(os.getenv("SCHEDULE_SEMESTER")) or 1
    blocks_count = _as_int(os.getenv("SCHEDULE_BLOCKS_COUNT")) or 2
    payload = {
        "course_id": course_id,
        "year": year,
        "semester": semester,
        "blocks_count": blocks_count,
    }
    
    print("Sending schedule request...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    # Send schedule request
    response = requests.post(f"{BASE_URL}/api/schedule/generate", json=payload)
    
    if response.status_code not in (200, 202):
        print(f"Error: {response.status_code}")
        print(response.text)
        return
    
    result = response.json()
    job_id = result.get("job_id")
    
    if not job_id:
        print("No job_id in response")
        print(result)
        return
    
    print(f"Job started with ID: {job_id}")
    
    # Monitor job status
    while True:
        status_response = requests.get(f"{BASE_URL}/api/schedule/status?job_id={job_id}")
        
        if status_response.status_code != 200:
            print(f"Status check error: {status_response.status_code}")
            break
        
        status = status_response.json()
        status_name = status.get("status")
        if status_name == "completed":
            result_preview = status.get("result") or []
            print(f"Status: completed (items={len(result_preview)})")
        elif status_name == "failed":
            print(f"Status: failed (error={status.get('error')})")
        else:
            print(f"Status: {status_name}")
        
        if status.get("status") in ["completed", "failed"]:
            break
        
        time.sleep(2)
    
    # Get final results if completed
    if status.get("status") == "completed":
        result_data = status.get("result") or []
        print("\nFinal schedule results:")

        blocks = {}
        scheduled_items = []
        unscheduled_items = []
        for item in result_data:
            blocks[item.get("block") or "?"] = blocks.get(item.get("block") or "?", 0) + 1
            if _as_int(item.get("day_id")) is None or _as_int(item.get("start_min")) is None or _as_int(item.get("end_min")) is None:
                unscheduled_items.append(item)
            else:
                scheduled_items.append(item)

        print(f"Base URL: {BASE_URL}")
        print(f"Total items: {len(result_data)}")
        
        print("\nRoom 15 (GS ER 7) occupants:")
        for item in scheduled_items:
            if str(item.get("room_id")) == "15":
                print(f"  {_item_label(item)}")
        
        print("\n=== Unscheduled 'GE - US' (ID 9) Details ===")
        for item in unscheduled_items:
            # Check subject_id in various formats
            sid = item.get("subject_id")
            if sid == 9 or sid == "9" or item.get("subject_code") == "GE - US":
                print(json.dumps(item, indent=2))

        print(f"Scheduled items: {len(scheduled_items)}")
        print(f"Unscheduled/placeholder items: {len(unscheduled_items)}")
        print(f"Items per block: {json.dumps(blocks, sort_keys=True)}")

        target_ids_raw = (os.getenv("TARGET_SUBJECT_IDS") or "").strip()
        target_ids = []
        if target_ids_raw:
            for part in target_ids_raw.split(","):
                val = _as_int(part.strip())
                if val is not None:
                    target_ids.append(val)
        if target_ids:
            target_matches = [
                it for it in result_data
                if _as_int(it.get("subject_id")) in target_ids or _as_int(it.get("clone_subject_id")) in target_ids
            ]
            print(f"Target subject matches ({target_ids}): {len(target_matches)}")
            for item in target_matches[:20]:
                print(f"  {_item_label(item)}")

        if unscheduled_items:
            unsched_ids = sorted({
                _as_int(it.get("subject_id")) or _as_int(it.get("clone_subject_id"))
                for it in unscheduled_items
                if _as_int(it.get("subject_id")) is not None or _as_int(it.get("clone_subject_id")) is not None
            })
            print(f"Unscheduled IDs (from placeholders): {unsched_ids}")

        room_conflicts = _collect_overlaps(
            scheduled_items,
            lambda it: (
                _as_int(it.get("day_id")),
                _as_int(it.get("room_id")),
            )
            if _as_int(it.get("room_id")) is not None
            else None,
        )
        instr_conflicts = _collect_overlaps(
            scheduled_items,
            lambda it: (
                _as_int(it.get("day_id")),
                _as_int(it.get("instructor_id")),
            )
            if _as_int(it.get("instructor_id")) is not None
            else None,
        )
        student_conflicts = _collect_overlaps(
            scheduled_items,
            lambda it: (
                _as_int(it.get("course_id")),
                _as_int(it.get("year")),
                it.get("block"),
                _as_int(it.get("day_id")),
            ),
        )

        print(f"Room conflicts: {len(room_conflicts)}")
        print(f"Instructor conflicts: {len(instr_conflicts)}")
        print(f"Student (within-block/day) conflicts: {len(student_conflicts)}")

        if room_conflicts:
            print("\nRoom conflict examples:")
            for key, a, b in room_conflicts[:10]:
                print(f"key={key}")
                print(f"  A: {_item_label(a)}")
                print(f"  B: {_item_label(b)}")

        if instr_conflicts:
            print("\nInstructor conflict examples:")
            for key, a, b in instr_conflicts[:10]:
                print(f"key={key}")
                print(f"  A: {_item_label(a)}")
                print(f"  B: {_item_label(b)}")

        if student_conflicts:
            print("\nStudent conflict examples:")
            for key, a, b in student_conflicts[:10]:
                print(f"key={key}")
                print(f"  A: {_item_label(a)}")
                print(f"  B: {_item_label(b)}")

        if os.getenv("PRINT_FULL_RESULTS") == "1":
            print("\nFull result payload:")
            print(json.dumps(result_data, indent=2))

if __name__ == "__main__":
    test_schedule()
