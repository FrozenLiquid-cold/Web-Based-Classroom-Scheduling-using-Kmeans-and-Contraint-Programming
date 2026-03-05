from api.db import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    with engine.connect() as conn:
        try:
            logger.info("Adding is_exit_point column...")
            conn.execute(text('ALTER TABLE curriculum_subjects ADD COLUMN is_exit_point BOOLEAN DEFAULT FALSE'))
            conn.commit()
            logger.info("Added is_exit_point.")
        except Exception as e:
            logger.warning(f"Failed to add is_exit_point (might already exist): {e}")
            conn.rollback()

        try:
            logger.info("Adding extra_info column...")
            conn.execute(text('ALTER TABLE curriculum_subjects ADD COLUMN extra_info TEXT'))
            conn.commit()
            logger.info("Added extra_info.")
        except Exception as e:
            logger.warning(f"Failed to add extra_info (might already exist): {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
