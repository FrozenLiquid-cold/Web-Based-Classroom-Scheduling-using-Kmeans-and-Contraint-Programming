# JRMSU Scheduler API

FastAPI backend for the K-Means and Constraint Programming Classroom Scheduling System.

## Setup

### 1. Install PostgreSQL

Make sure PostgreSQL is installed and running on your system.

### 2. Create Database

```sql
CREATE DATABASE jrmsu;
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and update the database URL:

```bash
cp .env.example .env
```

Edit `.env` and update `DATABASE_URL` with your PostgreSQL credentials:

```
DATABASE_URL=postgresql+psycopg2://username:password@localhost:5432/jrmsu
```

### 5. Initialize Database

```bash
python init_db.py
```

This will:
- Create all database tables
- Seed initial data (colleges, courses, instructors, days, subjects, rooms)
- Create default users:
  - `registrar` / `1234`
  - `instructor` / `1234`
  - `admin` / `1234`

### 6. Run the API Server

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/auth/login/{role}` - Login (role: admin, registrar, instructor)
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user info

### Entities (CRUD)
- `GET /api/colleges` - List all colleges
- `POST /api/colleges` - Create college
- `GET /api/colleges/{id}` - Get college
- `PUT /api/colleges/{id}` - Update college
- `DELETE /api/colleges/{id}` - Delete college

Same pattern for: `courses`, `instructors`, `days`, `subjects`, `rooms`

### Schedule
- `POST /api/schedule/generate` - Generate new schedule
- `POST /api/schedule/save` - Save schedule to database
- `GET /api/schedule/load` - Load schedule from database
- `DELETE /api/schedule/delete` - Delete schedule

## Database Schema

See `models.py` for the complete database schema. Key tables:
- `users` - User accounts and authentication
- `colleges` - Colleges
- `courses` - Courses (belongs to college)
- `instructors` - Instructors
- `days` - Days of the week (M, T, W, TH, F)
- `subjects` - Subjects (LEC or LAB type)
- `rooms` - Rooms (LEC or LAB type)
- `schedules` - Generated schedules

## Scheduler

The scheduler uses **OR-Tools Constraint Programming (CP-SAT)** to generate optimal class schedules. It automatically falls back to a greedy algorithm if OR-Tools is not available.

### Features
- **Constraint Programming**: Optimal schedule generation with complex constraints
- **Multi-objective Optimization**: Balances multiple scheduling preferences
- **Conflict Resolution**: Automatically avoids room and instructor double-booking
- **Greedy Fallback**: Fast algorithm for quick results

See `SCHEDULER.md` for detailed documentation and `scheduler/` directory for implementation.

## Integration with React Frontend

Update the React frontend to use the API instead of localStorage:

1. Update `src/store/db.js` to make API calls
2. Update `src/store/auth.js` to use API authentication
3. Update schedule generation to call `/api/schedule/generate`
4. Update schedule loading to call `/api/schedule/load`

## Development

### Running in Development Mode

```bash
uvicorn app:app --reload
```

### Database Migrations

For production, consider using Alembic for database migrations:

```bash
pip install alembic
alembic init migrations
```

## Production Deployment

1. Use a production WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. Use environment variables for configuration
3. Set up proper authentication (JWT tokens)
4. Use a reverse proxy (nginx) for HTTPS
5. Set up database backups

## License

MIT


