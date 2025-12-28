# K-Means Clustering for Course Scheduling

## Overview

K-Means clustering is used to group similar subjects and rooms together, which helps the constraint programming scheduler make better assignment decisions. This improves schedule quality by ensuring subjects with similar characteristics are scheduled together.

## Features

- **Subject Clustering**: Groups subjects by units, year level, semester, and recommended slots
- **Room Clustering**: Groups rooms by capacity and type
- **Automatic Min/Max Slots**: Calculates min and max slots based on subject type (LEC/LAB)
- **Cluster Matching**: Scheduler prefers matching subject clusters with room clusters

## Usage

### Via API

#### Cluster Subjects
```bash
POST /api/cluster/subjects?k=3&weight_slots=2.0
```

#### Cluster Rooms
```bash
POST /api/cluster/rooms?k=3
```

#### Cluster All
```bash
POST /api/cluster/all?k=3&cluster_rooms=true&weight_slots=2.0
```

### Via Python Script

```bash
# Cluster all subjects and rooms
python run_clustering.py all 3

# Cluster only subjects
python run_clustering.py subjects 5

# Cluster only rooms
python run_clustering.py rooms 3

# Cluster for specific course
python run_clustering.py all 3 1
```

### Via Python Code

```python
from db import SessionLocal
from clustering.kmeans_cluster import cluster_all

db = SessionLocal()

# Cluster subjects and rooms
result = cluster_all(db=db, k=3, cluster_rooms=True)

print(f"Clustered {result['subjects']['clustered_count']} subjects")
print(f"Clustered {result['rooms']['clustered_count']} rooms")
```

## Configuration

### Subject Features

Clustering uses these features for subjects:
- **unit**: Number of units
- **year_level**: Year level (1-4)
- **semester**: Semester (1-2)
- **recommended_slots**: Recommended time slots (weighted by `weight_slots`)

### Room Features

Clustering uses these features for rooms:
- **capacity**: Room capacity
- **type_encoded**: Room type (LEC=0, LAB=1)

### Parameters

- **k**: Number of clusters (default: 3)
- **weight_slots**: Weight multiplier for recommended_slots feature (default: 2.0)
- **random_state**: Random seed for reproducibility (default: 42)

## Min/Max Slots

After clustering, min and max slots are automatically calculated based on subject type:

- **LEC**: min_slots=2, max_slots=4
- **LAB**: min_slots=3, max_slots=3
- **Other**: min_slots=1, max_slots=4

These values are used by the scheduler to determine valid slot assignments.

## Database Fields

### Subject Fields
- `cluster`: Cluster ID assigned by K-Means
- `min_slots`: Minimum slots required
- `max_slots`: Maximum slots allowed
- `year_level`: Year level (for clustering)
- `semester`: Semester (for clustering)

### Room Fields
- `cluster`: Cluster ID assigned by K-Means
- `capacity`: Room capacity (for clustering)

## Migration

To add K-Means fields to existing database:

```bash
python migrate_add_kmeans_fields.py
```

This adds:
- `min_slots`, `max_slots` to subjects
- `year_level`, `semester` to subjects

## Workflow

### Typical Workflow

1. **Load Data**: Import subjects and rooms into database
2. **Set Year/Semester**: Set `year_level` and `semester` on subjects (if not set)
3. **Run Clustering**: Cluster subjects and rooms
4. **Generate Schedule**: Run scheduler (it will use cluster information)

### Example

```python
from db import SessionLocal
from clustering.kmeans_cluster import cluster_all
from scheduler.scheduler import run_scheduler

db = SessionLocal()

# 1. Cluster subjects and rooms
cluster_result = cluster_all(db=db, k=3, cluster_rooms=True)

# 2. Generate schedule (scheduler uses cluster information)
schedule = run_scheduler(
    db=db,
    course_id=1,
    year=1,
    semester=1,
    use_cp=True
)

# 3. Save schedule
from scheduler.scheduler import save_schedule
save_schedule(db, course_id=1, year=1, semester=1, schedule_items=schedule)
```

## Integration with Scheduler

The constraint programming scheduler uses cluster information to:

1. **Prefer Cluster Matching**: Subjects prefer rooms from the same cluster
2. **Optimize Assignments**: Cluster-based preferences improve schedule quality
3. **Handle Min/Max Slots**: Respects min_slots and max_slots constraints

## Troubleshooting

### Not Enough Subjects
If you have fewer subjects than clusters, the number of clusters will be automatically reduced.

### Missing Year/Semester
If `year_level` or `semester` is not set on subjects, defaults are used:
- `year_level`: 1
- `semester`: 1

### Missing Capacity
If room capacity is not set, a default of 30 is used for clustering.

## Statistics

After clustering, statistics are available:
- Number of subjects/rooms per cluster
- Average units per cluster
- Average slots per cluster
- Room type distribution per cluster

## References

- [scikit-learn K-Means](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html)
- [K-Means Algorithm](https://en.wikipedia.org/wiki/K-means_clustering)

