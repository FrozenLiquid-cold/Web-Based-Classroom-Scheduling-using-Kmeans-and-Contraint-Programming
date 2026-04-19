"""Authentication routes implemented with Flask blueprints."""
import hashlib
from typing import Optional, Tuple

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import models
from .. import schemas
from ..db import SessionLocal
from ..system_logger import log_event

auth_bp = Blueprint("auth", __name__)


def hash_password(password: str) -> str:
    """Simple password hashing (use bcrypt in production)."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password."""
    return hash_password(plain_password) == hashed_password


def _get_db_session() -> Session:
    """Create a new database session."""
    return SessionLocal()


def _extract_token() -> Optional[str]:
    """Extract bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return auth_header


def _get_current_user(db: Session) -> Tuple[Optional[models.User], Optional[Tuple[dict, int]]]:
    """Resolve the current user from the Authorization header."""
    token = _extract_token()
    if not token:
        return None, ({"detail": "Not authenticated"}, 401)

    try:
        username, role = token.split(":")
    except ValueError:
        return None, ({"detail": "Invalid token format"}, 401)

    user = (
        db.query(models.User)
        .filter(models.User.username == username, models.User.role == role)
        .first()
    )
    if not user:
        return None, ({"detail": "Invalid token"}, 401)
    return user, None


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login endpoint."""
    payload = request.get_json(force=True) or {}
    try:
        credentials = schemas.UserLogin(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = _get_db_session()
    try:
        user = (
            db.query(models.User)
            .filter(models.User.username == credentials.username)
            .first()
        )
        if not user or not verify_password(credentials.password, user.password_hash):
            log_event('auth', 'login_failed', f'Failed login attempt for "{credentials.username}"', level='WARNING')
            return jsonify({"detail": "Invalid credentials"}), 401

        log_event('auth', 'login', f'{user.username} logged in as {user.role}', user=user.username)
        return jsonify(
            {
                "role": user.role,
                "username": user.username,
                "instructor_id": user.instructor_id,
            }
        )
    finally:
        db.close()


@auth_bp.route("/profile", methods=["PUT"])
def update_profile():
    """Update the authenticated user's profile.

    For instructors, this allows changing username, password, and
    eligible class codes (assignable_courses) for their Instructor
    record. A fresh token is returned if the username changes.
    """

    payload = request.get_json(force=True) or {}
    try:
        update_data = schemas.UserProfileUpdate(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = _get_db_session()
    try:
        user, error = _get_current_user(db)
        if error:
            return jsonify(error[0]), error[1]

        # Track whether username changed so we can return a fresh token
        username_changed = False

        # Update username if provided and different
        if update_data.username and update_data.username != user.username:
            # Ensure uniqueness
            existing = (
                db.query(models.User)
                .filter(models.User.username == update_data.username)
                .first()
            )
            if existing and existing.id != user.id:
                return jsonify({"detail": "Username already exists"}), 400

            user.username = update_data.username
            # Also reflect on linked Instructor.username if present
            if user.instructor_id:
                instr = db.query(models.Instructor).get(user.instructor_id)
                if instr is not None:
                    instr.username = update_data.username
            username_changed = True

        # Update password if provided
        if update_data.password:
            user.password_hash = hash_password(update_data.password)

        # Update instructor assignable_courses if provided
        if update_data.assignable_courses is not None and user.instructor_id:
            instr = db.query(models.Instructor).get(user.instructor_id)
            if instr is not None:
                instr.assignable_courses = update_data.assignable_courses or None

        # Update instructor teaching preferences if provided
        if user.instructor_id:
            instr = db.query(models.Instructor).get(user.instructor_id)
            if instr is not None:
                if update_data.preferred_start_time is not None:
                    instr.preferred_start_time = update_data.preferred_start_time or None
                if update_data.preferred_end_time is not None:
                    instr.preferred_end_time = update_data.preferred_end_time or None
                if update_data.max_units is not None:
                    instr.max_units = update_data.max_units

        db.commit()

        # Build response similar to login_by_role
        token = f"{user.username}:{user.role}" if username_changed else None
        response = {
            "ok": True,
            "role": user.role,
            "username": user.username,
            "instructor_id": user.instructor_id,
        }
        if token:
            response["token"] = token

        return jsonify(response)
    finally:
        db.close()


@auth_bp.route("/login/<role>", methods=["POST"])
def login_by_role(role: str):
    """Login endpoint with role validation."""
    if role not in {"admin", "registrar", "instructor"}:
        return jsonify({"detail": "Invalid role"}), 400

    payload = request.get_json(force=True) or {}
    try:
        credentials = schemas.UserLogin(**payload)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    db = _get_db_session()
    try:
        user = (
            db.query(models.User)
            .filter(
                models.User.username == credentials.username,
                models.User.role == role,
            )
            .first()
        )
        if not user or not verify_password(credentials.password, user.password_hash):
            log_event('auth', 'login_failed', f'Failed login as {role} for "{credentials.username}"', level='WARNING')
            return jsonify({"detail": "Invalid credentials"}), 401

        log_event('auth', 'login', f'{user.username} logged in as {role}', user=user.username)
        token = f"{user.username}:{user.role}"
        return jsonify(
            {
                "ok": True,
                "token": token,
                "role": user.role,
                "username": user.username,
                "instructor_id": user.instructor_id,
            }
        )
    finally:
        db.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout endpoint (client should remove token)."""
    log_event('auth', 'logout', 'User logged out')
    return jsonify({"message": "Logged out successfully"})


@auth_bp.route("/me", methods=["GET"])
def get_current_user_info():
    """Get current user information."""
    db = _get_db_session()
    try:
        user, error = _get_current_user(db)
        if error:
            return jsonify(error[0]), error[1]
        return jsonify(
            {
                "role": user.role,
                "username": user.username,
                "instructor_id": user.instructor_id,
            }
        )
    finally:
        db.close()

