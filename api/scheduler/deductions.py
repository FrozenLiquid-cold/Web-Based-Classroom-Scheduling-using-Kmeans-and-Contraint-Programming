"""Shared helper to load designation deductions from the database."""
from ..db import SessionLocal
from .. import models


# Fallback defaults if the DB table is empty or unreachable
_DEFAULTS = {
    "program chair": 3,
    "college secretary": 3,
    "dean": 12,
    "associate dean": 12,
    "director": 12,
}


def get_deduction_map(session=None):
    """Return a dict mapping lowercase designation -> deduction_hours.

    If a session is provided, use it; otherwise open a new one.
    Falls back to hardcoded defaults if the table is empty or on error.
    """
    try:
        if session:
            rows = session.query(models.DesignationDeduction).all()
        else:
            db = SessionLocal()
            try:
                rows = db.query(models.DesignationDeduction).all()
            finally:
                db.close()

        if rows:
            return {r.designation.strip().lower(): r.deduction_hours for r in rows}
    except Exception:
        pass

    return dict(_DEFAULTS)


def get_designated_roles(session=None):
    """Return the set of designation names that have deductions."""
    return set(get_deduction_map(session).keys())
