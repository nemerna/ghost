"""Database connection and initialization for Jira MCP."""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from jira_mcp.db.models import Base

logger = logging.getLogger(__name__)


# =============================================================================
# Database Migrations
# =============================================================================

MIGRATIONS = [
    # Migration 1: Add ticket_source and github_repo to activity_log
    {
        "id": "001_add_ticket_source",
        "description": "Add ticket_source and github_repo columns to activity_log",
        "check": lambda inspector: "ticket_source" not in [
            c["name"] for c in inspector.get_columns("activity_log")
        ],
        "sql": [
            "ALTER TABLE activity_log ADD COLUMN ticket_source VARCHAR(10) DEFAULT 'jira' NOT NULL",
            "ALTER TABLE activity_log ADD COLUMN github_repo VARCHAR(255)",
        ],
    },
]


class Database:
    """Database connection manager supporting SQLite and PostgreSQL."""

    def __init__(self, database_url: str | None = None):
        """
        Initialize database connection.

        Args:
            database_url: Database URL. Defaults to environment variable or SQLite.
                - SQLite: sqlite:///path/to/db.sqlite
                - PostgreSQL: postgresql://user:pass@host:port/dbname
        """
        self._database_url = database_url or self._get_database_url()

        # Create engine with appropriate settings
        if self._database_url.startswith("sqlite"):
            # SQLite-specific settings
            self._engine = create_engine(
                self._database_url,
                connect_args={"check_same_thread": False},
                echo=False,
            )
        else:
            # PostgreSQL settings
            self._engine = create_engine(
                self._database_url,
                pool_size=5,
                max_overflow=10,
                echo=False,
            )

        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )

        logger.info(f"Database initialized: {self._get_safe_url()}")

    def _get_database_url(self) -> str:
        """Get database URL from environment or use default SQLite."""
        url = os.environ.get("DATABASE_URL")
        if url:
            return url

        # Default to SQLite in data directory
        data_dir = Path(os.environ.get("JIRA_MCP_DATA_DIR", "./data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir}/jira_mcp.db"

    def _get_safe_url(self) -> str:
        """Get database URL with password masked for logging."""
        if "@" in self._database_url:
            # Mask password in URL
            parts = self._database_url.split("@")
            prefix = parts[0].rsplit(":", 1)[0]
            return f"{prefix}:***@{parts[1]}"
        return self._database_url

    def create_tables(self) -> None:
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self._engine)
        logger.info("Database tables created/verified")
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run pending database migrations."""
        inspector = inspect(self._engine)
        
        # Check if activity_log table exists before running migrations
        if "activity_log" not in inspector.get_table_names():
            logger.info("activity_log table doesn't exist yet, skipping migrations")
            return

        for migration in MIGRATIONS:
            try:
                if migration["check"](inspector):
                    logger.info(f"Running migration: {migration['id']} - {migration['description']}")
                    with self._engine.connect() as conn:
                        for sql in migration["sql"]:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                                logger.info(f"  Executed: {sql[:50]}...")
                            except Exception as e:
                                # Column might already exist in some edge cases
                                if "duplicate column" in str(e).lower():
                                    logger.warning(f"  Column already exists, skipping: {sql[:50]}...")
                                else:
                                    raise
                    logger.info(f"Migration {migration['id']} completed")
                else:
                    logger.debug(f"Migration {migration['id']} already applied")
            except Exception as e:
                logger.error(f"Migration {migration['id']} failed: {e}")
                # Don't raise - allow app to continue with potentially degraded functionality

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Get a database session as a context manager."""
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session(self) -> Session:
        """Get a new database session (caller must close it)."""
        return self._session_factory()


# Global database instance
_db_instance: Database | None = None


def init_db(database_url: str | None = None) -> Database:
    """
    Initialize the global database instance.

    Args:
        database_url: Optional database URL override.

    Returns:
        The initialized Database instance.
    """
    global _db_instance
    _db_instance = Database(database_url)
    _db_instance.create_tables()
    return _db_instance


def get_db() -> Database:
    """
    Get the global database instance, initializing if needed.

    Returns:
        The Database instance.
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.create_tables()
    return _db_instance
