# Project Analysis & Codebase Questions - Answers

## 🔧 PROJECT & CODEBASE QUESTIONS

### 1. Languages & Frameworks

**What programming languages does your project use?**
- **Python 3.8+** (Backend API)
- **JavaScript/JSX** (Frontend - React)
- **SQL** (PostgreSQL database)

**What primary frameworks or libraries are involved?**
- **Backend:**
  - Flask 3.0.0 (Web framework)
  - SQLAlchemy 2.0.23 (ORM)
  - Pydantic 2.5.0 (Data validation)
  - OR-Tools 9.8.3296 (Constraint Programming solver)
  - scikit-learn 1.3.2 (K-Means clustering)
  - psycopg2-binary 2.9.9 (PostgreSQL adapter)
  - Flask-CORS 4.0.0 (Cross-origin resource sharing)

- **Frontend:**
  - React 18.2.0 (UI framework)
  - React Router DOM 6.27.0 (Routing)
  - Vite 5.4.8 (Build tool & dev server)
  - Tailwind CSS 3.4.15 (Styling)
  - PostCSS & Autoprefixer (CSS processing)

### 2. Project Structure

**How is the codebase organized?**
- **Single project** (not a monorepo)
- Clear separation between frontend and backend

**What are the major folders/modules?**

```
SchedulerUI/
├── api/                          # Backend (Python/Flask)
│   ├── routes/                   # API route handlers
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── entities.py          # CRUD for colleges, courses, etc.
│   │   ├── schedule.py          # Schedule generation endpoints
│   │   └── clustering.py        # K-Means clustering endpoints
│   ├── scheduler/                # Scheduling algorithms
│   │   ├── scheduler.py         # Main scheduler coordinator
│   │   ├── cp_scheduler.py      # OR-Tools CP-SAT solver
│   │   ├── greedy.py            # Greedy fallback algorithm
│   │   ├── course_scheduler.py  # Course-level scheduling
│   │   └── timeslots.py         # Time slot utilities
│   ├── clustering/               # K-Means clustering
│   │   └── kmeans_cluster.py
│   ├── migrations/               # Database migrations
│   ├── models.py                # SQLAlchemy ORM models
│   ├── schemas.py               # Pydantic validation schemas
│   ├── db.py                    # Database connection & session
│   ├── db_helpers.py            # Database helper functions
│   ├── db_procedures.py         # Stored procedures
│   ├── app.py                   # Flask application entry point
│   └── run.py                   # Development server runner
│
├── src/                          # Frontend (React)
│   ├── pages/                   # Page components
│   │   ├── Admin/               # Admin pages
│   │   ├── Auth/                # Login pages
│   │   ├── Instructor/          # Instructor pages
│   │   ├── Registrar/           # Registrar pages (main CRUD)
│   │   └── User/                # Shared user pages
│   ├── layouts/                 # Layout components
│   │   ├── AdminLayout.jsx
│   │   ├── InstructorLayout.jsx
│   │   └── RegistrarLayout.jsx
│   ├── services/                # API service layer
│   │   └── api.js               # API client functions
│   ├── store/                   # State management
│   │   ├── auth.js              # Authentication state
│   │   └── db.js                # Data persistence (legacy)
│   ├── utils/                   # Utility functions
│   │   └── schedule.js
│   ├── styles/                  # Global styles
│   │   ├── tailwind.css
│   │   └── theme.css
│   ├── data/                    # Mock data (legacy)
│   │   └── mockData.js
│   ├── App.jsx                  # Main app component & routing
│   └── main.jsx                 # React entry point
│
├── public/                       # Static assets
├── dist/                         # Production build output
├── docs/                         # Documentation
└── postgres_and_data.sql        # Database schema & seed data
```

### 3. Development Environment

**What IDE are you using?**
- **Cursor** (based on VS Code, with AI integration)

**Are there any existing AI integrations I should be aware of?**
- You're using Cursor, which has built-in AI assistance
- No other explicit AI integrations in the codebase

### 4. Code Style & Conventions

**Do you follow a specific style guide?**
- **Python:**
  - No explicit `.pylintrc` or `pyproject.toml` found
  - Code appears to follow PEP 8 conventions (snake_case, docstrings)
  - Uses type hints in some places (e.g., `_get_session() -> SessionLocal`)
  - Docstrings use triple quotes (`"""`)
  
- **JavaScript/React:**
  - No `.eslintrc` or `.prettierrc` found in root
  - Uses camelCase for variables/functions
  - Uses JSX with functional components
  - Uses hooks (useState, useEffect)
  - No semicolons in some files (e.g., `App.jsx`)

**Should the assistant match a certain tone or verbosity in code comments?**
- Comments are concise and functional
- Docstrings explain purpose and parameters
- No excessive verbosity observed
- **Recommendation:** Match existing style - clear, concise, purposeful

---

## 🗂 DATABASE STRUCTURE

**What database do you use?**
- **PostgreSQL** (version 17.0.04 based on SQL dump)
- Database name: `Scheduler_DB` (or `jrmsu` in some configs)

**Are your tables/models structured in a specific way?**
- **ORM-based:** SQLAlchemy models in `api/models.py`
- **Naming convention:**
  - Tables: plural, lowercase (e.g., `users`, `colleges`, `schedules`)
  - Columns: snake_case (e.g., `first_name`, `college_id`)
  - Foreign keys: `{table}_id` pattern (e.g., `instructor_id`, `room_id`)
  - Primary keys: `id` (Integer, auto-increment)

**Key Tables:**
- `users` - Authentication (username, password_hash, role)
- `colleges` - Academic departments
- `courses` - Academic programs (belongs to college)
- `instructors` - Teachers (belongs to college)
- `subjects` - Course subjects (LEC/LAB types)
- `rooms` - Classrooms (LEC/LAB types, capacity)
- `days` - Days of week (M, T, W, TH, F)
- `schedules` - Generated schedule entries
- `time_blocks` - Time slot definitions
- `timeslots` - Time slot candidates
- `candidates` - Scheduling candidates

**Do you use an ORM?**
- **Yes, SQLAlchemy 2.0.23**
- Declarative base: `Base = declarative_base()`
- Relationships defined with `relationship()` and `back_populates`
- Session management via `SessionLocal` (sessionmaker)
- Connection pooling configured (pool_size=10, max_overflow=20)

**Database Features:**
- Unique constraints (e.g., `uq_room_time`, `uq_instructor_time`)
- Check constraints (e.g., role validation, type validation)
- Foreign key relationships
- Indexes on primary keys and foreign keys
- Stored procedures (in `db_procedures.py`)

---

## 📋 TASK TRACKING

**How are tasks formatted in project_specs.md?**
- **File does not exist** - No `project_specs.md` found in the codebase
- Documentation exists in markdown files:
  - `HOW_TO_RUN.md` - Setup instructions
  - `SYSTEM_FLOW.md` - System architecture & flow
  - `FRONTEND_API_INTEGRATION.md` - Integration notes
  - Various optimization/fix docs in `api/` folder

**Should the assistant update tasks automatically or always ask for confirmation?**
- **Recommendation:** Ask for confirmation before:
  - Modifying database schema
  - Changing core scheduling logic
  - Breaking API changes
  - Auto-update is fine for:
    - Code style fixes
    - Bug fixes in non-critical paths
    - Documentation updates

**Do tasks have statuses (e.g., TODO / IN PROGRESS / DONE) or priorities?**
- No formal task tracking system found
- Documentation files mention completed items with ✅ checkmarks
- **Recommendation:** Consider adding a `project_specs.md` or `TODO.md` if needed

---

## 🧩 ASSISTANT BEHAVIOR

**Should the assistant be proactive (suggest tasks, warn about smells, infer context) or reactive only?**
- **Current state:** Reactive (responding to user queries)
- **Recommendation:** 
  - **Proactive for:**
    - Code quality issues (unused imports, potential bugs)
    - Performance optimizations
    - Security concerns (e.g., hardcoded credentials)
    - Best practices (e.g., error handling, async/await patterns)
  - **Reactive for:**
    - Feature requests
    - Bug fixes (unless critical)
    - Major refactoring

**Should it remember long-term project details across sessions?**
- **Yes** - The assistant should remember:
  - Project structure and architecture
  - Database schema and relationships
  - API endpoint patterns
  - Code style preferences
  - Common patterns used (e.g., async API calls, error handling)

**Any hard restrictions?**
- **Yes:**
  1. **Never modify database schema without explicit confirmation**
  2. **Never change core scheduling algorithms without discussion**
  3. **Never commit credentials or sensitive data**
  4. **Never break existing API contracts without versioning**
  5. **Always test database migrations on a copy first**
  6. **Preserve backward compatibility when possible**

---

## 🔒 Security & Data Sensitivity

**Does your project contain sensitive info?**
- **Yes:**
  - User passwords (hashed, but still sensitive)
  - Database credentials (in `.env` file - not in repo, but should be protected)
  - Default credentials documented: `registrar/1234`, `instructor/1234`, `admin/1234`
  - Academic data (instructors, courses, schedules)

**Are there rules I must enforce?**
- **Yes:**
  1. **Never generate production credentials** - Only use test/dev credentials
  2. **Never recommend schema changes without confirmation** - Database changes are critical
  3. **Never expose `.env` files** - Keep them in `.gitignore`
  4. **Never hardcode passwords or API keys** - Always use environment variables
  5. **Never skip authentication checks** - All protected routes must verify user role
  6. **Never recommend disabling CORS in production** - Current `CORS(app, resources={r"/*": {"origins": "*"}})` is for dev only
  7. **Always validate user input** - Use Pydantic schemas on backend
  8. **Always use parameterized queries** - SQLAlchemy handles this, but verify

**Security Observations:**
- ✅ Passwords are hashed (stored as `password_hash`)
- ✅ SQLAlchemy prevents SQL injection
- ✅ Pydantic validates input
- ⚠️ CORS allows all origins (`*`) - should be restricted in production
- ⚠️ No JWT tokens implemented (commented out in requirements.txt)
- ⚠️ Default passwords are weak (`1234`)

---

## 📄 ADDITIONAL INFORMATION

### Sample Directory Tree (Key Files)

```
SchedulerUI/
├── api/
│   ├── app.py                    # Flask app entry
│   ├── models.py                 # SQLAlchemy models
│   ├── db.py                     # Database connection
│   ├── schemas.py                # Pydantic schemas
│   ├── routes/                   # API routes
│   ├── scheduler/                # Scheduling algorithms
│   └── requirements.txt          # Python dependencies
├── src/
│   ├── App.jsx                   # React routing
│   ├── main.jsx                  # React entry
│   ├── services/api.js           # API client
│   ├── pages/                    # Page components
│   └── layouts/                  # Layout components
├── package.json                  # Node dependencies
├── vite.config.js                # Vite configuration
├── tailwind.config.cjs           # Tailwind config
└── postgres_and_data.sql         # Database schema
```

### Representative Code Snippet

**Backend (Flask Route):**
```python
@schedule_bp.route("/course", methods=["POST"])
def schedule_course_endpoint():
    """Schedule a single course for a specific year/semester using KMeans + CP-SAT."""
    payload = request.get_json(force=True) or {}
    # Validation and processing...
```

**Frontend (React Component):**
```jsx
async function onSave(e) {
    e.preventDefault()
    try {
        await upsert('entity', item)
        await load()
    } catch (error) {
        setError(error.message || 'Failed to save')
    }
}
```

**Database Model:**
```python
class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    # ... relationships and constraints
```

### Key Patterns Observed

1. **API Communication:**
   - Frontend uses `fetch()` with timeout handling
   - Base URL: `http://localhost:8000/api`
   - Error handling with try/catch
   - Async/await pattern

2. **Database Access:**
   - Session management via `SessionLocal()`
   - Context managers for cleanup
   - Transaction handling

3. **Scheduling:**
   - K-Means clustering for grouping
   - OR-Tools CP-SAT for optimization
   - Greedy fallback if CP-SAT fails
   - Cluster-based processing

4. **Error Handling:**
   - Try/catch blocks in async functions
   - Error messages returned as JSON
   - Logging with Python's `logging` module

---

## 📝 SUMMARY

This is a **full-stack classroom scheduling system** for JRMSU (Jose Rizal Memorial State University) with:
- **Backend:** Flask + SQLAlchemy + OR-Tools (constraint programming)
- **Frontend:** React + Vite + Tailwind CSS
- **Database:** PostgreSQL
- **Architecture:** RESTful API with role-based access (admin, registrar, instructor)
- **Core Feature:** Automated schedule generation using K-Means clustering + constraint programming

The codebase is well-organized with clear separation of concerns. The assistant should be proactive about code quality and security, but always confirm before making breaking changes or database modifications.

