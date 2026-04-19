"""API endpoints for system logs."""
from flask import Blueprint, request, jsonify
from sqlalchemy import desc
from ..db import SessionLocal
from ..models import SystemLog

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/system-logs", methods=["GET"])
def get_system_logs():
    """Fetch system logs with optional filters and pagination."""
    db = SessionLocal()
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        category = request.args.get("category", "")
        level = request.args.get("level", "")
        search = request.args.get("search", "")

        per_page = min(per_page, 200)

        query = db.query(SystemLog).order_by(desc(SystemLog.timestamp))

        if category:
            query = query.filter(SystemLog.category == category)
        if level:
            query = query.filter(SystemLog.level == level)
        if search:
            like = f"%{search}%"
            query = query.filter(
                (SystemLog.detail.ilike(like)) |
                (SystemLog.action.ilike(like)) |
                (SystemLog.user.ilike(like))
            )

        total = query.count()
        logs = query.offset((page - 1) * per_page).limit(per_page).all()

        return jsonify({
            "logs": [
                {
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                    "level": log.level,
                    "category": log.category,
                    "action": log.action,
                    "user": log.user,
                    "detail": log.detail,
                    "metadata": log.metadata_json,
                }
                for log in logs
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@logs_bp.route("/system-logs/clear", methods=["DELETE"])
def clear_system_logs():
    """Clear all system logs."""
    db = SessionLocal()
    try:
        count = db.query(SystemLog).count()
        db.query(SystemLog).delete()
        db.commit()
        # Log the clear action itself
        from ..system_logger import log_event
        log_event("system", "clear_logs", f"Cleared {count} log entries", level="WARNING")
        return jsonify({"message": f"Cleared {count} log entries"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
