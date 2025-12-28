"""Expose Flask blueprints for application registration."""
from .auth import auth_bp
from .entities import entities_bp
from .schedule import schedule_bp

try:
    from .clustering import clustering_bp
except ImportError:  # pragma: no cover - optional
    clustering_bp = None

__all__ = [
    "auth_bp",
    "entities_bp",
    "schedule_bp",
    "clustering_bp",
]

