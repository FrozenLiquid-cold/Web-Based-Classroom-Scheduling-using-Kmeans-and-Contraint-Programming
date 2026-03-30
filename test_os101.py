import sys
sys.path.insert(0, '.')
from api.db import SessionLocal
from api.db_procedures import get_subjects_for_scheduling
from api.scheduler.cp_scheduler import _is_nstp_subject

session = SessionLocal()
subs = get_subjects_for_scheduling(session, course_id=4)
focus = [72, 64, 65, 66, 67, 68, 69, 74, 71, 70, 73]
subjects = [s for s in subs if getattr(s, 'id', None) in focus]

print(f"Initial: {[s.code for s in subjects if s.id == 66]}")

# NSTP handling
non_nstp_subjects = [s for s in subjects if not _is_nstp_subject(s)]
subjects = non_nstp_subjects

print(f"After NSTP filter: {[s.code for s in subjects if s.id == 66]}")

# Expand subjects
block_count = 3
try:
    max_subject_id = max(int(getattr(s, "id")) for s in subjects if getattr(s, "id", None) is not None)
except Exception:
    max_subject_id = 0

id_stride = max_subject_id + 1 if max_subject_id is not None else 1000000
expanded_subjects = []

for subj in subjects:
    subj_id_val = getattr(subj, "id", None)
    if subj_id_val == 66:
        print(f"Found OS 101 in expand loop, ID: {subj_id_val}")
    try:
        subj_id_int = int(subj_id_val)
    except Exception as e:
        print(f"Error casting: {e}")
        continue

    for student_block_index in range(1, block_count + 1):
        new_id = subj_id_int + student_block_index * id_stride
        if subj_id_val == 66:
            print(f"Creating clone for block {student_block_index}: {new_id}")
        
        class _SubjectBlockClone: pass
        clone = _SubjectBlockClone()
        for attr_name, attr_value in subj.__dict__.items():
            if attr_name.startswith("_"): continue
            setattr(clone, attr_name, attr_value)
        setattr(clone, "id", new_id)
        setattr(clone, "original_subject_id", subj_id_int)
        setattr(clone, "student_block", student_block_index)
        expanded_subjects.append(clone)

subjects = expanded_subjects
print(f"After expand: {[s.code for s in subjects if getattr(s, 'original_subject_id', None) == 66]}")

session.close()
