"""Quick script to verify diagnostics structure for unscheduled subjects."""
import sys, json
sys.path.insert(0, '.')
from api.db import SessionLocal
from api.scheduler.scheduler import run_scheduler

db = SessionLocal()
try:
    items, diags = run_scheduler(
        db, course_id=3, years=[4], semester=1, blocks_count=2,
        use_kmeans=True, k_clusters=3
    )
    print("=" * 60)
    print("DIAGNOSTICS STRUCTURE")
    print("=" * 60)
    print(f"Top-level keys: {list(diags.keys())}")

    ur = diags.get("unscheduled_reasons", {})
    print(f"unscheduled_reasons count: {len(ur)}")
    for sid, entry in ur.items():
        reason = entry.get("reason", entry.get("failure_reason", "?"))
        recs = entry.get("recommendations", [])
        suggestion = entry.get("suggestion", "")
        print(f"  Subject {sid}:")
        print(f"    reason = {reason}")
        print(f"    suggestion = {suggestion}")
        print(f"    recommendations count = {len(recs)}")
        if recs:
            for i, r in enumerate(recs[:3]):
                print(f"      rec[{i}]: room={r.get('room_name')}, day={r.get('day_label')}, time={r.get('time')}, score={r.get('score')}")

    # Check _raw too
    raw = diags.get("_raw", {})
    print(f"\n_raw diagnostics count: {len(raw)}")
    for sid, entry in raw.items():
        if isinstance(entry, dict):
            reason = entry.get("failure_reason", "?")
            recs = entry.get("recommendations", [])
            print(f"  _raw[{sid}]: reason={reason}, recs={len(recs)}")

    # Show missing items
    missing = [it for it in items if it.get("day_id") is None]
    print(f"\nPlaceholder (unscheduled) items count: {len(missing)}")
    for m in missing:
        print(f"  subject_id={m.get('subject_id')}, block={m.get('block')}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
