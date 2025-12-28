# How to Run the SchedulerUI Application

## Prerequisites

1. **PostgreSQL** must be installed and running
2. **Python 3.8+** installed
3. **Node.js** and **npm** installed (for frontend)

## Step 1: Create the Database

Make sure PostgreSQL is running, then create the database:

```sql
CREATE DATABASE "Scheduler_DB";
```

You can do this via:
- **pgAdmin**: Right-click "Databases" → Create → Database → Name: `Scheduler_DB`
- **psql command line**: `psql -U postgres -c 'CREATE DATABASE "Scheduler_DB";'`

## Step 2: Backend Setup (API Server)

### 2.1 Install Python Dependencies

```bash
cd api
pip install -r requirements.txt
```

### 2.2 Initialize Database

The `.env` file is already configured with:
- Database: `Scheduler_DB`
- Password: `ara`
- User: `postgres`

If you have existing tables with a different schema, you may need to drop them first:

```sql
-- Connect to Scheduler_DB
\c "Scheduler_DB"

-- Drop all tables (if needed)
DROP TABLE IF EXISTS schedules CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS subjects CASCADE;
DROP TABLE IF EXISTS rooms CASCADE;
DROP TABLE IF EXISTS instructors CASCADE;
DROP TABLE IF EXISTS days CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS colleges CASCADE;
```

Then run:

```bash
cd api
python init_db.py
```

This will:
- Create all database tables
- Seed initial data (colleges, courses, instructors, days, subjects, rooms)
- Create default users:
  - `registrar` / `1234`
  - `instructor` / `1234`
  - `admin` / `1234`

### 2.3 Start the API Server

```bash
cd api
python run.py
```

The API will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

**Keep this terminal window open** - the server needs to keep running.

## Step 3: Frontend Setup (React App)

Open a **new terminal window** and run:

### 3.1 Install Node Dependencies

```bash
npm install
```

### 3.2 Start the Development Server

```bash
npm run dev
```

The frontend will be available at:
- **Frontend**: http://localhost:5173

## Step 4: Access the Application

1. Open your browser and go to: **http://localhost:5173**
2. Login with one of the default accounts:
   - **Registrar**: `registrar` / `1234`
   - **Instructor**: `instructor` / `1234`
   - **Admin**: `admin` / `1234`

## Troubleshooting

### Database Connection Error

If you see: `password authentication failed` or `database does not exist`

**Solution**:
1. Verify PostgreSQL is running
2. Check the `.env` file in `api/` folder has correct credentials
3. Verify the database `Scheduler_DB` exists

### Port Already in Use

If port 8000 (backend) or 5173 (frontend) is already in use:

**Backend**: Edit `api/.env` and change `API_PORT=8001`
**Frontend**: Vite will automatically use the next available port

### Tables Already Exist Error

If you get schema mismatch errors, drop and recreate the tables (see Step 2.2)

## Quick Commands Summary

```bash
# Terminal 1 - Backend
cd api
python run.py

# Terminal 2 - Frontend  
npm run dev
```

Both servers need to be running simultaneously for the application to work!

