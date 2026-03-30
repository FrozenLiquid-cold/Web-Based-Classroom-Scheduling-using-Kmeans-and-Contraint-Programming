"""Migration: Remove flawed schedule unique constraints.

The old constraints (uq_room_time_block_course, uq_instructor_time_block_course)
included course_id, which was too permissive — allowing the same room/instructor
to be double-booked across courses.

However, we CANNOT add stricter constraints because shared rooms like FIELD
legitimately host multiple courses + blocks simultaneously (NSTP). A simple
UNIQUE constraint cannot distinguish shared rooms from exclusive rooms.

Conflict prevention is handled by the CP scheduler's in-memory checks, which
correctly account for shared rooms, NSTP rules, and all edge cases. The DB
constraints are removed rather than incorrectly tightened.
"""
from sqlalchemy import text
from .db import engine
import logging

logger = logging.getLogger(__name__)


def ensure_fixed_schedule_constraints():
    """Remove flawed unique constraints that gave false safety."""
    with engine.connect() as conn:
        try:
            # Check if old constraints exist
            result = conn.execute(text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'schedules'
                  AND constraint_type = 'UNIQUE'
                  AND constraint_name IN (
                      'uq_room_time_block_course',
                      'uq_instructor_time_block_course',
                      'uq_room_time_block',
                      'uq_instructor_time_block',
                      'uq_room_time',
                      'uq_instructor_time'
                  )
            """))
            old_constraints = [row[0] for row in result]

            if not old_constraints:
                logger.info("No flawed schedule constraints found, skipping migration 016.")
                return

            # Drop ALL constraint variants
            for name in old_constraints:
                conn.execute(text(
                    f'ALTER TABLE schedules DROP CONSTRAINT IF EXISTS {name}'
                ))
                logger.info("Dropped constraint: %s", name)

            conn.commit()
            logger.info(
                "Migration 016 applied: Removed %d flawed schedule constraints. "
                "Conflict prevention is handled by the CP scheduler.",
                len(old_constraints)
            )
        except Exception as e:
            logger.error("Migration 016 failed: %s", e)
            raise


if __name__ == "__main__":
    ensure_fixed_schedule_constraints()
