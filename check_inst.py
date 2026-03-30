import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api'))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api'))
from api.db import SessionLocal
from api.models import Instructor
db = SessionLocal()
instructors = db.query(Instructor).all()
for inst in instructors:
    mu = getattr(inst, 'max_units', 'N/A')
    print(f"  id={inst.id}, name='{inst.first_name} {inst.last_name}', max_units={mu}")
db.close()
