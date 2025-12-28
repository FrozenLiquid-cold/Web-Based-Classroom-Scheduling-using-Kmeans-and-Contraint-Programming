# Quick Start Guide

## ✅ What's Been Created

A complete **FastAPI + PostgreSQL backend** for your JRMSU Scheduler with:

- ✅ **Database models** (SQLAlchemy) - colleges, courses, instructors, days, subjects, rooms, schedules, users
- ✅ **API routes** - Authentication, CRUD operations, Schedule generation/load/save
- ✅ **Scheduler integration** - Greedy algorithm (working) + OR-Tools placeholder (ready for implementation)
- ✅ **Database initialization** - Script to create tables and seed data
- ✅ **Migration tool** - Import existing localStorage data to PostgreSQL
- ✅ **Documentation** - Complete setup and integration guides

## 🚀 Quick Setup (3 Steps)

### 1. Install Dependencies
```bash
cd api
pip install -r requirements.txt
```

### 2. Configure Database
```bash
# Create .env file
cp config_template.env .env

# Edit .env and update DATABASE_URL:
# DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/jrmsu

# Create database in PostgreSQL:
# CREATE DATABASE jrmsu;
```

### 3. Initialize & Run
```bash
# Initialize database (creates tables + seed data)
python init_db.py

# Start API server
python run.py
```

API will be available at **http://localhost:8000**
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/health

## 📁 File Structure

```
api/
├── app.py                    # Main FastAPI application
├── db.py                     # Database connection
├── models.py                 # SQLAlchemy models
├── schemas.py                # Pydantic schemas
├── init_db.py                # Database initialization
├── run.py                    # Server startup
├── requirements.txt          # Python dependencies
├── routes/
│   ├── auth.py              # Authentication endpoints
│   ├── entities.py          # CRUD endpoints
│   └── schedule.py          # Schedule endpoints
└── scheduler/
    ├── scheduler.py         # Main scheduler (OR-Tools placeholder)
    └── greedy.py            # Greedy algorithm (fallback)
```

## 🔑 Default Users

After running `init_db.py`, you can login with:
- **Registrar:** `registrar` / `1234`
- **Instructor:** `instructor` / `1234`
- **Admin:** `admin` / `1234`

## 📡 API Endpoints

### Authentication
- `POST /api/auth/login/{role}` - Login (role: admin, registrar, instructor)

### Entities (CRUD)
- `GET /api/{entity}` - List all
- `POST /api/{entity}` - Create
- `GET /api/{entity}/{id}` - Get by ID
- `PUT /api/{entity}/{id}` - Update
- `DELETE /api/{entity}/{id}` - Delete

**Entities:** `colleges`, `courses`, `instructors`, `days`, `subjects`, `rooms`

### Schedule
- `POST /api/schedule/generate` - Generate schedule
- `POST /api/schedule/save` - Save schedule
- `GET /api/schedule/load` - Load schedule
- `DELETE /api/schedule/delete` - Delete schedule

## 🔄 Next Steps

1. **Test the API:**
   - Visit http://localhost:8000/docs
   - Try the endpoints interactively

2. **Update React Frontend:**
   - See `INTEGRATION_GUIDE.md` for detailed instructions
   - Create `src/services/api.js` with API calls
   - Update `src/store/db.js` to use API instead of localStorage
   - Update `src/store/auth.js` to use API authentication

3. **Migrate Existing Data (Optional):**
   ```bash
   # Export localStorage data from browser console:
   # JSON.stringify(JSON.parse(localStorage.getItem('jrmsu')))
   # Save to exported_data.json
   
   python migrate_from_localstorage.py exported_data.json
   ```

4. **Implement OR-Tools (Optional):**
   - Install: `pip install ortools`
   - Implement constraint programming in `scheduler/scheduler.py`
   - See commented example code in the file

## 📚 Documentation

- **Setup Guide:** `SETUP.md` - Complete setup instructions
- **Integration Guide:** `INTEGRATION_GUIDE.md` - Frontend integration
- **API Documentation:** http://localhost:8000/docs (when server is running)

## ⚠️ Troubleshooting

**Database Connection Error:**
- Check PostgreSQL is running: `pg_isready`
- Verify DATABASE_URL in `.env`
- Check database exists: `psql -U postgres -l`

**Import Errors:**
- Install dependencies: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.8+)

**CORS Errors:**
- Verify CORS origins in `app.py` include your frontend URL
- Check API server is running

## 🎯 Architecture

```
React Frontend (Vite)
    ↓ HTTP/REST
FastAPI Backend
    ↓ SQLAlchemy ORM
PostgreSQL Database
```

- **Frontend:** React SPA (existing)
- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL (shared data layer)
- **Scheduler:** Python (greedy algorithm, OR-Tools ready)

## ✨ Key Features

- ✅ Unified backend (Python) and frontend (React)
- ✅ Persistent, queryable data (Postgres)
- ✅ Clean migration path from localStorage
- ✅ Ready for multi-user and web deployment
- ✅ Keeps your existing scheduling logic (no rewrite needed)
- ✅ OR-Tools integration ready (placeholder structure)

---

**Ready to integrate!** See `INTEGRATION_GUIDE.md` for frontend updates.

