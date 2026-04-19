"""Utility for writing system log entries."""
import json
from datetime import datetime
from .db import SessionLocal
from .models import SystemLog


def log_event(category, action, detail=None, user=None, level='INFO', metadata=None):
    """Write a single log entry to the system_logs table.

    Args:
        category: auth | schedule | entity | settings | system
        action:   login | logout | generate | create | update | delete | resolve | error ...
        detail:   Human-readable description
        user:     Username who triggered it (optional)
        level:    INFO | WARNING | ERROR | SUCCESS
        metadata: dict of extra structured data (optional, stored as JSON)
    """
    db = SessionLocal()
    try:
        entry = SystemLog(
            level=level,
            category=category,
            action=action,
            user=user,
            detail=detail,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[SystemLog] Failed to write log: {e}")
    finally:
        db.close()
