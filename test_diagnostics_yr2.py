"""Test diagnostics with year 2 where subjects are more likely to fail."""
import sys
sys.path.insert(0, '.')
from api.db import SessionLocal
from api.scheduler.scheduler import run_scheduler

db = SessionLocal()
try:
    items, diags = run_scheduler(
        db, course_id=3, years=[2], semester=1, blocks_count=2,
        use_kmeans=True, k_clusters=3
    )
    print("=" * 60)
    print("DIAGNOSTICS STRUCTURE (Year 2)")
    print("=" * 60)
    print(f"Top-level keys: {list(diags.keys())}")
    print(f"solver_status: {diags.get('solver_status')}")
    print(f"subjects_scheduled: {diags.get('subjects_scheduled')}")
    print(f"subjects_total: {diags.get('subjects_total')}")

    ur = diags.get("unscheduled_reasons", {})
    print(f"\nunscheduled_reasons count: {len(ur)}")
    for sid, entry in ur.items():
        reason = entry.get("reason", "?")
        recs = entry.get("recommendations", [])
        suggestion = entry.get("suggestion", "")
        detail = entry.get("reason_text", "")
        print(f"  Subject {sid}:")
        print(f"    reason       = {reason}")
        print(f"    reason_text  = {detail}")
        print(f"    suggestion   = {suggestion}")
        print(f"    recs count   = {len(recs)}")
        if recs:
            for i, r in enumerate(recs[:3]):
                print(f"      rec[{i}]: room={r.get('room_name')}, day={r.get('day_label')}, time={r.get('time')}, instr={r.get('instructor_name')}, score={r.get('score')}")

    # Check _raw too
    raw = diags.get("_raw", {})
    print(f"\n_raw diagnostics count: {len(raw)}")
    for sid, entry in list(raw.items())[:5]:
        if isinstance(entry, dict):
            reason = entry.get("failure_reason", "?")
            recs = entry.get("recommendations", [])
            print(f"  _raw[{sid}]: reason={reason}, recs={len(recs)}")

    # Show unscheduled placeholder items
    missing = [it for it in items if it.get("day_id") is None]
    print(f"\nPlaceholder (unscheduled) items: {len(missing)}")
    for m in missing:
        print(f"  subject_id={m.get('subject_id')}, block={m.get('block')}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
