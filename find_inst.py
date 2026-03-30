"""Find NoOverlap/AtMostOne/instructor conflict constraints in CP model"""
with open('api/scheduler/cp_scheduler.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Search within run_cp_scheduler (2908-7491) for instructor overlap constraints
for i in range(2907, min(7491, len(lines))):
    line = lines[i]
    lower = line.lower()
    if any(kw in lower for kw in ['nooverlap', 'no_overlap', 'atmoston', 'at_most_one',
           'instr.*conflict', 'instructor.*clash', 'same.*instructor.*time',
           'instr.*overlap', 'instructor.*constraint']):
        try:
            print(f"{i+1}: {line.rstrip()[:140]}")
        except:
            print(f"{i+1}: [encoding error]")
