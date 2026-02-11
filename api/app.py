"""Flask application for JRMSU Scheduler."""
import logging
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

# Import db module to ensure models are registered
from .db import Base, engine, init_db
from .migrate_restore_room_capacity import (
    ensure_capacity_column,
    ensure_schedule_subject_nullable,
)
from .migrate_instructor_load_fields import ensure_instructor_load_fields
from .migrate_schedule_details_view import ensure_schedule_details_view
from .migrate_subject_major_flag import ensure_subject_major_flag
from .migrate_subject_year_sem_fields import ensure_subject_year_sem_fields
from .routes.auth import auth_bp
from .routes.entities import entities_bp
from .routes.schedule import schedule_bp
from .routes.buildings import buildings_bp
from .routes.validation import validation_bp
from .routes.swap_requests import swap_requests_bp
from .routes.curriculum import curriculum_bp
from .routes.stats import stats_bp

try:
    from .routes.clustering import clustering_bp
except ImportError:  # pragma: no cover - optional blueprint
    clustering_bp = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize the Flask application
app = Flask(__name__)

# Configure CORS with permissive settings for development
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Allow all origins for development
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": ["*"],  # Allow all headers
        "supports_credentials": True,
        "expose_headers": ["*"],
        "max_age": 600
    }
})

# Initialize the database
init_db()

# Ensure required schema migrations are applied after database is initialized
ensure_capacity_column()
ensure_schedule_subject_nullable()
ensure_instructor_load_fields()
ensure_schedule_details_view()
ensure_subject_major_flag()
ensure_subject_year_sem_fields()

# Request timing middleware
@app.before_request
def _start_timer():
    request._start_time = time.time()

@app.after_request
def _log_request(response):
    if hasattr(request, '_start_time'):
        duration = (time.time() - request._start_time) * 1000
        logger.info(f"Request {request.method} {request.path} took {duration:.2f}ms")
    return response

# Error handling
@app.errorhandler(Exception)
def handle_exception(exc):
    logger.exception("An error occurred during request")
    return jsonify({"error": "Internal server error"}), 500

# Register blueprints (matching previous FastAPI prefixes)
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(entities_bp, url_prefix="/api")
app.register_blueprint(schedule_bp, url_prefix="/api/schedule")
app.register_blueprint(buildings_bp, url_prefix="/api/buildings")
app.register_blueprint(validation_bp, url_prefix="/api/validate")
app.register_blueprint(swap_requests_bp)
app.register_blueprint(curriculum_bp, url_prefix="/api")
app.register_blueprint(stats_bp, url_prefix="/api/stats")

if clustering_bp:
    app.register_blueprint(clustering_bp, url_prefix="/api")

# Root endpoint
@app.route("/")
def root():
    """Root endpoint that provides API information."""
    return jsonify({
        "name": "JRMSU Scheduler API",
        "version": "1.0.0",
        "endpoints": {
            "instructors": "/api/instructors",
            "courses": "/api/courses",
            "subjects": "/api/subjects",
            "rooms": "/api/rooms",
            "days": "/api/days",
            "auth": "/api/auth",
            "schedule": "/api/schedule"
        }
    })

# Backward compatibility routes
@app.route("/api/schedule/course", methods=["POST"])
def schedule_course_proxy():
    """Backward-compatible proxy for the React client."""
    from .routes.schedule import schedule_course_endpoint
    return schedule_course_endpoint()

# Add a catch-all route for 404 errors
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested URL was not found on the server.",
        "status": 404
    }), 404

# Health check endpoint
@app.route("/health")
def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return jsonify({"status": "healthy"})

# In app.py, at the bottom of the file, add:
if __name__ == "__main__":
    # Initialize the database
    from .db import init_db
    init_db()
    
    # Run the app
    app.run(host="0.0.0.0", port=8000, debug=True)