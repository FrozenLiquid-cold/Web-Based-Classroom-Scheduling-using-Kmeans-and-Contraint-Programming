"""Database connection and session management"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL from environment variable
# Format: postgresql+psycopg2://user:password@host:port/database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/Scheduler_DB"
)

# Create engine with timeout settings for long-running operations
connect_args = {
    "connect_timeout": 10,  # Connection timeout in seconds
}

# If using PostgreSQL, disable statement timeout for long-running queries
if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    # Set statement_timeout to 0 (unlimited) for long-running schedule generation
    # This will be set per-connection when the connection is created
    connect_args["options"] = "-c statement_timeout=0"

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",  # Set to True for SQL logging
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    pool_size=10,        # Maintain a pool of up to 10 connections
    max_overflow=20,     # Allow up to 20 connections during high load
    connect_args=connect_args,
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a base class for declarative class definitions
# This should be imported by models.py to define models
Base = declarative_base()

# Flag to track if models have been imported
_models_imported = False

def import_models():
    """Import models to ensure they are registered with SQLAlchemy"""
    global _models_imported
    if not _models_imported:
        # Import models here to avoid circular imports
        from . import models  # noqa: F401
        _models_imported = True

# Create all tables in the database
def init_db():
    """
    Initialize the database by creating all tables.
    This should be called after all models are imported.
    """
    # Import models to ensure they are registered with SQLAlchemy
    import_models()
    
    # Create all tables with extend_existing=True to prevent redefinition errors
    Base.metadata.create_all(bind=engine, checkfirst=True)


# Dependency for FastAPI to get DB session
def get_db():
    """Get database session for dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
