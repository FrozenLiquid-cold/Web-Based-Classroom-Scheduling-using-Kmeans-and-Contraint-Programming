# JRMSU Classroom Scheduling System - Basic Flow

## 🏗️ System Architecture Overview

The system consists of:
- **Frontend**: React (Vite) - User interface
- **Backend**: FastAPI (Python) - API server
- **Database**: SQLite/PostgreSQL - Data storage
- **Scheduling Engine**: OR-Tools CP-SAT (with K-Means clustering + Greedy fallback)

---

## 📊 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│                    (React Frontend)                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Registrar Schedule Page (Schedule.jsx)                  │   │
│  │  - Select College                                        │   │
│  │  - Click "Regenerate" Button                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API SERVICE LAYER                            │
│                  (src/services/api.js)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  generateSchedule(courseId, year, semester)              │   │
│  │  - Makes POST request to /api/schedule/generate          │   │
│  │  - Shows loading state & progress                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼ HTTP POST Request
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND API ROUTE                            │
│              (api/routes/schedule.py)                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  @router.post("/generate")                               │   │
│  │  - Validates course exists                               │   │
│  │  - Calls run_scheduler()                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SCHEDULER COORDINATOR                          │
│              (api/scheduler/scheduler.py)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  run_scheduler()                                         │   │
│  │                                                          │   │
│  │  STEP 1: K-Means Clustering (if enabled)                 │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  - Groups subjects into clusters based on:         │  │   │
│  │  │    • Units                                         │  │   │
│  │  │    • Year level                                    │  │   │
│  │  │    • Semester                                      │  │   │
│  │  │    • Recommended slots (weighted)                  │  │   │
│  │  │  - Groups rooms into clusters                      │  │   │
│  │  │  - Assigns cluster IDs to subjects & rooms         │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                                                          │   │
│  │  STEP 2: Constraint Programming Solver                   │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  Try OR-Tools CP-SAT solver:                       │  │   │
│  │  │  - If available → use CP solver                    │  │   │
│  │  │  - If fails → fallback to greedy                   │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                                                          │   │
│  │  STEP 3: Greedy Fallback (if CP fails)                   │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │  Simple first-fit greedy algorithm                 │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              CONSTRAINT PROGRAMMING SCHEDULER                     │
│          (api/scheduler/cp_scheduler.py)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  run_cp_scheduler()                                       │  │
│  │                                                            │  │
│  │  1. Load Data:                                            │  │
│  │     - Subjects (filtered by course/year/sem)             │  │
│  │     - Instructors                                        │  │
│  │     - Rooms                                               │  │
│  │     - Days                                                │  │
│  │     - Existing bookings                                  │  │
│  │                                                            │  │
│  │  2. Build Eligibility Maps:                              │  │
│  │     - course_to_instructors (by college matching)         │  │
│  │     - course_to_rooms (by type: LEC/LAB)                  │  │
│  │                                                            │  │
│  │  3. Group by Clusters:                                   │  │
│  │     - Process subjects cluster by cluster                │  │
│  │     - Prevents conflicts between clusters               │  │
│  │                                                            │  │
│  │  4. For Each Cluster:                                    │  │
│  │     ┌──────────────────────────────────────────────────┐ │  │
│  │     │  a) Greedy Initial Schedule (warm-start hints)  │ │  │
│  │     │     - Quick first-fit assignment                 │ │  │
│  │     │     - Provides hints to CP solver                │ │  │
│  │     │                                                    │ │  │
│  │     │  b) Build CP Model:                              │ │  │
│  │     │     - Create decision variables for each         │ │  │
│  │     │       (subject, room, start_slot, instructor)   │ │  │
│  │     │     - Add constraints:                           │ │  │
│  │     │       • No room double-booking                    │ │  │
│  │     │       • No instructor double-booking              │ │  │
│  │     │       • Consecutive time slots                   │ │  │
│  │     │       • Room type matching (LEC/LAB)             │ │  │
│  │     │       • Capacity constraints                      │ │  │
│  │     │       • LEC/LAB linking                            │ │  │
│  │     │                                                    │ │  │
│  │     │  c) Set Objective:                               │ │  │
│  │     │     - Maximize scheduled subjects                │ │  │
│  │     │     - Minimize cluster mismatches                │ │  │
│  │     │     - Prefer later time slots                     │ │  │
│  │     │     - Fill lunch gaps                            │ │  │
│  │     │     - Avoid early morning (7:30 AM)               │ │  │
│  │     │                                                    │ │  │
│  │     │  d) Apply Hints:                                  │ │  │
│  │     │     - Use greedy initial schedule as hints       │ │  │
│  │     │                                                    │ │  │
│  │     │  e) Solve:                                       │ │  │
│  │     │     - Run CP-SAT solver                           │ │  │
│  │     │     - Max time: 120 seconds                       │ │  │
│  │     │                                                    │ │  │
│  │     │  f) Extract Solution:                           │ │  │
│  │     │     - Convert solver results to schedule items   │ │  │
│  │     │     - Update global bookings                     │ │  │
│  │     └──────────────────────────────────────────────────┘ │  │
│  │                                                            │  │
│  │  5. Return All Scheduled Items                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RESPONSE BACK TO API                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  {                                                         │  │
│  │    "status": "success",                                   │  │
│  │    "course_id": 1,                                        │  │
│  │    "year": 1,                                             │  │
│  │    "semester": 1,                                         │  │
│  │    "items": [                                             │  │
│  │      {                                                     │  │
│  │        "subject_id": 1,                                  │  │
│  │        "instructor_id": 5,                               │  │
│  │        "room_id": 3,                                      │  │
│  │        "day_id": 1,                                       │  │
│  │        "time": "8:00–10:00"                               │  │
│  │      },                                                    │  │
│  │      ...                                                   │  │
│  │    ],                                                      │  │
│  │    "count": 25                                            │  │
│  │  }                                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND DISPLAY                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  - Updates state with schedule items                      │  │
│  │  - Displays in table format                              │  │
│  │  - Shows: Subject, Day, Room, Time, Instructor            │  │
│  │  - User can save to database                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Detailed Step-by-Step Flow

### **Phase 1: User Initiates Scheduling**

1. **User selects a College** in the Schedule page
2. **User clicks "Regenerate" button**
3. **Frontend sets loading state** (`isGenerating = true`)
4. **Shows loading overlay** with progress indicator

### **Phase 2: API Request**

1. **Frontend calls** `api.generateSchedule(courseId, year, semester)`
2. **HTTP POST** to `http://localhost:8000/api/schedule/generate`
3. **Request body**:
   ```json
   {
     "course_id": 1,
     "year": 1,
     "semester": 1,
     "subject_ids": null,
     "use_kmeans": true,
     "k_clusters": 3
   }
   ```

### **Phase 3: Backend Processing**

#### **3.1 Route Handler** (`api/routes/schedule.py`)
- Validates course exists
- Calls `run_scheduler()`

#### **3.2 Scheduler Coordinator** (`api/scheduler/scheduler.py`)

**Step 1: K-Means Clustering** (if enabled)
- Groups subjects into clusters based on:
  - Units
  - Year level
  - Semester
  - Recommended slots (weighted)
- Groups rooms into clusters
- Assigns cluster IDs to subjects and rooms
- **Purpose**: Reduces problem complexity by grouping similar items

**Step 2: Constraint Programming**
- Tries to use OR-Tools CP-SAT solver
- If unavailable or fails → falls back to greedy

#### **3.3 CP Scheduler** (`api/scheduler/cp_scheduler.py`)

**For each cluster:**

1. **Load Data**
   - Subjects (filtered by course/year/semester)
   - Instructors
   - Rooms
   - Days
   - Existing bookings (to avoid conflicts)

2. **Build Eligibility Maps**
   - `course_to_instructors`: Which instructors can teach which subjects
     - Matches by college
     - Checks assignable_courses
   - `course_to_rooms`: Which rooms are suitable for which subjects
     - Matches by type (LEC/LAB)

3. **Greedy Initial Schedule** (warm-start)
   - Quick first-fit assignment
   - Provides hints to CP solver
   - Marks booked slots to prevent double-booking

4. **Build CP Model**
   - **Decision Variables**: Boolean for each (subject, room, start_slot, instructor, duration)
   - **Constraints**:
     - Each subject scheduled at most once
     - No room double-booking
     - No instructor double-booking
     - Consecutive time slots required
     - Room type must match subject type
     - Capacity constraints
     - LEC/LAB linking (same instructor)
   
5. **Set Objective Function**
   - Maximize: Number of scheduled subjects
   - Minimize: Cluster mismatches
   - Prefer: Later time slots, lunch fill, avoid 7:30 AM

6. **Apply Hints**
   - Uses greedy initial schedule as hints
   - Helps solver find solution faster

7. **Solve**
   - Runs CP-SAT solver
   - Max time: 120 seconds
   - Uses multiple workers for parallel search

8. **Extract Solution**
   - Converts solver results to schedule items
   - Updates global bookings for next cluster

### **Phase 4: Response & Display**

1. **Backend returns** schedule items as JSON
2. **Frontend receives** response
3. **Updates state** with schedule data
4. **Displays in table**:
   - Subject code, description, type, units
   - Day, Room, Time, Instructor
5. **User can save** to database

---

## 🔑 Key Components

### **Frontend**
- `src/pages/Registrar/Schedule.jsx` - Main schedule UI
- `src/services/api.js` - API communication layer
- `src/store/db.js` - Data persistence layer

### **Backend**
- `api/routes/schedule.py` - API endpoints
- `api/scheduler/scheduler.py` - Main scheduler coordinator
- `api/scheduler/cp_scheduler.py` - OR-Tools CP solver
- `api/scheduler/greedy.py` - Greedy fallback algorithm
- `api/clustering/kmeans_cluster.py` - K-Means clustering

### **Database Models**
- `Subject` - Courses to schedule
- `Instructor` - Teachers
- `Room` - Classrooms
- `Day` - Days of week
- `Schedule` - Generated schedule entries
- `Course` - Academic programs
- `College` - Departments

---

## 🎯 Key Features

1. **K-Means Clustering**: Groups similar subjects/rooms to reduce complexity
2. **Constraint Programming**: Solves complex scheduling with hard constraints
3. **Greedy Warm-Start**: Provides initial hints to CP solver
4. **Cluster-based Processing**: Processes subjects in batches to prevent conflicts
5. **Progress Tracking**: Shows real-time progress during generation
6. **Loading States**: Prevents multiple clicks and shows feedback

---

## 📝 Data Flow Summary

```
User Action
    ↓
Frontend API Call
    ↓
Backend Route Handler
    ↓
Scheduler Coordinator
    ↓
K-Means Clustering (optional)
    ↓
CP Scheduler (per cluster)
    ├─→ Greedy Initial Schedule
    ├─→ Build CP Model
    ├─→ Apply Constraints
    ├─→ Set Objective
    ├─→ Apply Hints
    ├─→ Solve
    └─→ Extract Solution
    ↓
Combine All Clusters
    ↓
Return Schedule Items
    ↓
Frontend Display
```

---

This system uses advanced optimization techniques (K-Means + Constraint Programming) to automatically generate conflict-free class schedules while respecting all constraints and preferences.

