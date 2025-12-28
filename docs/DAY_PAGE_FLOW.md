# Day Page - Complete Flow & Logic

## 📋 Overview
This document traces the complete flow when a user clicks "Day" in the Registrar UI, from navigation to data operations.

---

## 🔄 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER CLICKS "DAY" IN NAVIGATION                             │
│    Location: src/layouts/RegistrarLayout.jsx (line 9)           │
│    - NavLink with to="/r/day"                                    │
│    - React Router handles navigation                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. ROUTE MATCHING                                               │
│    Location: src/App.jsx (line 50)                               │
│    - Route: path="/r/day" element={<Day />}                    │
│    - Guard checks authentication (role="registrar")            │
│    - If authenticated → render Day component                    │
│    - If not → redirect to /login/registrar                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. DAY COMPONENT MOUNTS                                         │
│    Location: src/pages/Registrar/Day.jsx                        │
│                                                                  │
│    Initial State:                                               │
│    - items: [] (empty array)                                    │
│    - q: '' (search query)                                      │
│    - show: false (modal visibility)                            │
│    - editing: null (currently editing item)                     │
│    - label: '' (form input)                                     │
│    - error: '' (validation errors)                              │
│    - entries: 10 (pagination limit)                            │
│    - dataLoadingRef: false (prevents duplicate loads)          │
│    - dataLoadedRef: false (tracks if data loaded)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. useEffect TRIGGERS ON MOUNT                                  │
│    Location: src/pages/Registrar/Day.jsx (line 34)              │
│    - useEffect(() => { load() }, [])                            │
│    - Empty dependency array = runs once on mount               │
│    - Calls load() function                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. load() FUNCTION EXECUTES                                     │
│    Location: src/pages/Registrar/Day.jsx (lines 17-33)          │
│                                                                  │
│    Step 5.1: Check Duplicate Prevention                         │
│    - if (dataLoadedRef.current || dataLoadingRef.current)       │
│      → return (skip if already loading/loaded)                  │
│                                                                  │
│    Step 5.2: Set Loading Flag                                    │
│    - dataLoadingRef.current = true                              │
│                                                                  │
│    Step 5.3: Call list('day')                                   │
│    - await list('day') → goes to src/store/db.js                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CACHE CHECK IN db.js                                         │
│    Location: src/store/db.js (lines 24-44)                      │
│                                                                  │
│    Step 6.1: Get Cache from window                               │
│    - const { cache, pending } = getCache()                      │
│    - Uses window.__dbListCache (persists across reloads)        │
│                                                                  │
│    Step 6.2: Check Cache                                         │
│    - cached = cache.get('day')                                  │
│    - If cached && age < 30s → return cached.data (NO API CALL)  │
│                                                                  │
│    Step 6.3: Check Pending Requests                               │
│    - if (pending.has('day')) → return pending promise            │
│    - Prevents duplicate concurrent requests                     │
│                                                                  │
│    Step 6.4: Create New Request (if not cached/pending)         │
│    - Create promise for API call                                │
│    - Store in pending.set('day', promise)                       │
│    - Return promise                                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. API CALL TO BACKEND                                          │
│    Location: src/services/api.js (lines 62-70)                  │
│                                                                  │
│    Step 7.1: Entity Mapping                                      │
│    - entity = 'day'                                             │
│    - backendEntity = ENTITY_MAP['day'] || 'day' = 'days'       │
│                                                                  │
│    Step 7.2: Build Request                                       │
│    - URL: http://localhost:8000/api/days                        │
│    - Method: GET                                                 │
│    - Headers: Content-Type: application/json                     │
│    - Headers: Authorization: Bearer {token} (if exists)         │
│                                                                  │
│    Step 7.3: Execute Fetch                                       │
│    - fetch(`${API_URL}/days`, { ... })                          │
│    - Timeout: 5 minutes (300000ms)                             │
│    - AbortController for cancellation                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. BACKEND API PROCESSING                                       │
│    Location: api/routes/entities.py (lines 203-206)             │
│                                                                  │
│    Step 8.1: Route Handler                                       │
│    - @router.get("/days")                                        │
│    - Function: list_days(db: Session)                            │
│                                                                  │
│    Step 8.2: Database Query                                      │
│    - db.query(models.Day).all()                                 │
│    - Returns all Day records from database                       │
│                                                                  │
│    Step 8.3: Response Serialization                             │
│    - response_model=List[schemas.DayResponse]                     │
│    - Converts SQLAlchemy models to Pydantic schemas             │
│    - Returns JSON array: [{id: 1, label: "M"}, ...]            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. RESPONSE PROCESSING                                          │
│    Location: src/store/db.js (lines 49-59)                      │
│                                                                  │
│    Step 9.1: Parse Response                                      │
│    - const data = await api.list(entity)                        │
│    - result = Array.isArray(data) ? data : []                   │
│                                                                  │
│    Step 9.2: Cache Result                                        │
│    - cache.set('day', { data: result, timestamp: Date.now() })  │
│    - Stores in window.__dbListCache for 30 seconds              │
│                                                                  │
│    Step 9.3: Cleanup Pending                                     │
│    - setTimeout(() => pending.delete('day'), 500ms)             │
│    - Removes from pending requests after 500ms                   │
│                                                                  │
│    Step 9.4: Return Data                                         │
│    - return result (array of day objects)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. UPDATE COMPONENT STATE                                      │
│     Location: src/pages/Registrar/Day.jsx (lines 26-27)         │
│                                                                  │
│     - setItems(data) → updates items state                      │
│     - dataLoadedRef.current = true                              │
│     - dataLoadingRef.current = false                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. RENDER TABLE                                                │
│     Location: src/pages/Registrar/Day.jsx (lines 36-43, 119)   │
│                                                                  │
│     Step 11.1: Filter Data (useMemo)                            │
│     - filtered = items.filter(label includes q)                │
│     - Recomputes when items or q changes                        │
│                                                                  │
│     Step 11.2: Paginate Data (useMemo)                           │
│     - shown = filtered.slice(0, entries)                        │
│     - Limits display to 'entries' count                        │
│                                                                  │
│     Step 11.3: Render Table                                      │
│     - Maps over 'shown' array                                   │
│     - Displays: No., Day Label, Edit/Delete buttons            │
└─────────────────────────────────────────────────────────────────┘

---

## 🎯 User Interactions Flow

### A. ADD DAY
```
User clicks "Add Day" button
  ↓
openAdd() called (line 45)
  ↓
- setEditing(null)
- setLabel('')
- setError('')
- setShow(true) → Shows modal
  ↓
User enters label (e.g., "M") and clicks "Save"
  ↓
onSave(e) called (line 59)
  ↓
Validation:
  - if (!label.trim()) → setError('Day label is required')
  - Check duplicate → setError('Day must be unique')
  ↓
upsert('day', { id: editing?.id, label: label.trim() })
  ↓
src/store/db.js → upsert() (line 84)
  ↓
If editing?.id exists:
  → api.update('days', id, { label })
  → PUT /api/days/{id}
Else:
  → api.create('days', { label })
  → POST /api/days
  ↓
Backend: api/routes/entities.py
  - Creates/Updates Day in database
  - Returns DayResponse
  ↓
After success:
  - setShow(false) → Hide modal
  - await load() → Reload data
```

### B. EDIT DAY
```
User clicks Edit button on a row
  ↓
openEdit(it) called (line 52)
  ↓
- setEditing(it) → Store item being edited
- setLabel(it.label || '')
- setError('')
- setShow(true) → Shows modal with pre-filled data
  ↓
User modifies label and clicks "Save"
  ↓
Same flow as ADD, but editing?.id exists
  → Calls PUT /api/days/{id} instead of POST
```

### C. DELETE DAY
```
User clicks Delete button on a row
  ↓
onDelete(id) called (line 73)
  ↓
- confirm('Delete this day?') → Browser confirmation
  ↓
If confirmed:
  remove('day', id)
  ↓
src/store/db.js → remove() (line 98)
  ↓
api.remove('days', id)
  ↓
DELETE /api/days/{id}
  ↓
Backend: api/routes/entities.py (line 228)
  - db.delete(day)
  - db.commit()
  - Returns 204 No Content
  ↓
After success:
  - await load() → Reload data
```

### D. SEARCH/FILTER
```
User types in search box
  ↓
onChange={(e) => setQ(e.target.value)}
  ↓
q state updates
  ↓
filtered useMemo recalculates (line 36)
  ↓
- items.filter(i => label.toLowerCase().includes(q.toLowerCase()))
  ↓
shown useMemo recalculates (line 40)
  ↓
- filtered.slice(0, entries)
  ↓
Table re-renders with filtered results
```

---

## 📊 Data Flow Summary

```
┌─────────────┐
│   Browser   │
│   (React)   │
└──────┬──────┘
       │
       │ 1. User clicks "Day"
       │
       ▼
┌──────────────────┐
│  RegistrarLayout │  NavLink to="/r/day"
│  (Navigation)   │
└──────┬───────────┘
       │
       │ 2. React Router
       │
       ▼
┌──────────────────┐
│   App.jsx        │  Route matching
│   (Routing)      │  Guard check
└──────┬───────────┘
       │
       │ 3. Component Mount
       │
       ▼
┌──────────────────┐
│   Day.jsx        │  useEffect → load()
│   (Component)    │
└──────┬───────────┘
       │
       │ 4. Cache Check
       │
       ▼
┌──────────────────┐
│   db.js          │  list('day')
│   (Cache Layer)  │  - Check cache
│                  │  - Check pending
│                  │  - Create request
└──────┬───────────┘
       │
       │ 5. API Call
       │
       ▼
┌──────────────────┐
│   api.js         │  GET /api/days
│   (API Service)  │
└──────┬───────────┘
       │
       │ 6. HTTP Request
       │
       ▼
┌──────────────────┐
│   FastAPI        │  @router.get("/days")
│   (Backend)      │
└──────┬───────────┘
       │
       │ 7. Database Query
       │
       ▼
┌──────────────────┐
│   PostgreSQL     │  SELECT * FROM days
│   (Database)     │
└──────┬───────────┘
       │
       │ 8. Response
       │
       ▼
┌──────────────────┐
│   Day.jsx        │  setItems(data)
│   (Render)       │  → Table displays
└──────────────────┘
```

---

## 🔑 Key Files & Functions

| File | Purpose | Key Functions |
|------|---------|---------------|
| `src/layouts/RegistrarLayout.jsx` | Navigation | NavLink to="/r/day" |
| `src/App.jsx` | Routing | Route path="day" element={<Day />} |
| `src/pages/Registrar/Day.jsx` | UI Component | load(), openAdd(), openEdit(), onSave(), onDelete() |
| `src/store/db.js` | Cache Layer | list(), upsert(), remove() |
| `src/services/api.js` | API Service | list(), create(), update(), remove() |
| `api/routes/entities.py` | Backend Routes | list_days(), create_day(), delete_day() |
| `api/models.py` | Database Models | Day model |
| `api/db.py` | Database Connection | Session management |

---

## 🛡️ Safety Mechanisms

1. **Duplicate Prevention**: `dataLoadingRef` and `dataLoadedRef` prevent double-loading
2. **Cache Deduplication**: `pendingRequests` Map prevents concurrent API calls
3. **Error Handling**: All API calls wrapped in try/catch with fallbacks
4. **Validation**: Client-side validation before API calls (required fields, duplicates)
5. **Authentication**: Guard component checks role before rendering

---

## 📝 Notes

- **Cache TTL**: 30 seconds (data cached for 30s after first load)
- **Pending Cleanup**: 500ms delay before removing from pending requests
- **Search**: Client-side filtering (no API call on search)
- **Pagination**: Client-side slicing (no server-side pagination)
- **Modal**: Controlled by `show` state, pre-filled when editing


