"""Helper to load system settings from the database."""
from .. import models

# Defaults if DB is empty or unreachable
DEFAULTS = {
    "regular_base_hours": 24,
    "visiting_base_hours": 30,
}


def get_system_settings(session=None):
    """Return a dict of all system settings {key: value}.
    Values are returned as strings; use get_int() for numeric settings.
    """
    settings = dict(DEFAULTS)
    try:
        if session:
            rows = session.query(models.SystemSetting).all()
        else:
            from ..db import SessionLocal
            db = SessionLocal()
            try:
                rows = db.query(models.SystemSetting).all()
            finally:
                db.close()

        for r in rows:
            try:
                settings[r.key] = int(r.value)
            except (ValueError, TypeError):
                settings[r.key] = r.value
    except Exception:
        pass
    return settings


def get_setting(key, default=None, session=None):
    """Return a single setting value by key."""
    settings = get_system_settings(session)
    return settings.get(key, default)
