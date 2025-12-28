"""
Database helper utilities for safe transaction handling.

This module provides utilities to prevent transaction abort errors
by ensuring proper rollback on exceptions.
"""
from typing import Callable, Any, TypeVar
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@contextmanager
def safe_db_session(session_factory):
    """
    Context manager for safe database sessions with automatic rollback on error.
    
    Usage:
        with safe_db_session(SessionLocal) as db:
            result = db.query(Model).all()
            db.commit()
    """
    db = session_factory()
    try:
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error: {e}", exc_info=True)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in database operation: {e}", exc_info=True)
        raise
    finally:
        db.close()


def safe_query(db: Session, query_func: Callable[[Session], T]) -> T:
    """
    Execute a database query with automatic rollback on error.
    
    Args:
        db: Database session
        query_func: Function that takes a session and returns a result
    
    Returns:
        Result from query_func
    
    Example:
        result = safe_query(db, lambda s: s.query(Model).all())
    """
    try:
        return query_func(db)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database query error: {e}", exc_info=True)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Query error: {e}", exc_info=True)
        raise


def safe_commit(db: Session) -> None:
    """
    Safely commit a transaction with rollback on error.
    
    Args:
        db: Database session
    """
    try:
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Commit error: {e}", exc_info=True)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during commit: {e}", exc_info=True)
        raise

