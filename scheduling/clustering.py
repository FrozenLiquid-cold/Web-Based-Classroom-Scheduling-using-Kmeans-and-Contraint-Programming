import random
from .utils import *
from .scheduler import *
from copy import deepcopy

# ------------------------------
# Simple K-Means (pure Python)
# ------------------------------
def kmeans(data, k=2, max_iters=100):
    # data: list of lists [[x1, x2, x3], ...]
    # Random initial centroids
    centroids = random.sample(data, k)
    clusters = [0] * len(data)
    
    for _ in range(max_iters):
        new_clusters = []
        # Assign each point to nearest centroid
        for point in data:
            dists = [sum((p-c)**2 for p,c in zip(point, centroid)) for centroid in centroids]
            new_clusters.append(dists.index(min(dists)))
        
        if new_clusters == clusters:
            break
        clusters = new_clusters
        
        # Recompute centroids
        for i in range(k):
            assigned_points = [p for idx,p in enumerate(data) if clusters[idx]==i]
            if assigned_points:
                centroids[i] = [sum(dim)/len(dim) for dim in zip(*assigned_points)]
    return clusters

# ------------------------------
# Encode courses to numeric vectors
# ------------------------------
def encode_courses(courses, instructors, timeslots):
    vectors = []
    for c in courses:
        # Units in minutes
        units_min = int(c['Units']) * 60
        
        # Type encoding: LEC=0, LAB=1
        type_val = 0 if c['Type'].upper() == 'LEC' else 1
        
        # Number of instructors who can teach this course
        instructor_count = sum(1 for i in instructors 
                               if c['Code'].replace(" ","").lower() in i["Assignable_Courses"].replace(" ","").lower())
        
        # Day preference: ratio of available MW slots
        available_slots = [ts for ts in timeslots if int(ts['Duration_Minutes']) >= units_min]
        mw_count = sum(1 for ts in available_slots if ts['Days'] == 'MW')
        tth_count = sum(1 for ts in available_slots if ts['Days'] == 'TTh')
        total_slots = mw_count + tth_count
        day_pref = mw_count / total_slots if total_slots > 0 else 0.5  # default 0.5 if no info
        
        vectors.append([units_min, type_val, instructor_count, day_pref])
    return vectors

