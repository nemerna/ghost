"""Database connection and initialization for Ghost."""

import logging
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from ghost.db.models import Base

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
    # Migration 2: Drop one_liner and executive_summary from management_reports
    # These columns are no longer needed - reports now only store content (bullet list)
    # Note: SQLite < 3.35.0 doesn't support DROP COLUMN, so the columns may remain
    # but won't be used. This is safe - they're just ignored by the application.
    {
        "id": "002_simplify_management_reports",
        "description": "Drop one_liner and executive_summary columns from management_reports",
        "check": lambda inspector: "management_reports" in inspector.get_table_names()
        and "one_liner" in [c["name"] for c in inspector.get_columns("management_reports")],
        "sql": [
            # PostgreSQL and SQLite 3.35.0+ support DROP COLUMN
            "ALTER TABLE management_reports DROP COLUMN one_liner",
            "ALTER TABLE management_reports DROP COLUMN executive_summary",
        ],
        "optional": True,  # Allow failure on older SQLite - columns will remain but unused
    },
    # Migration 3: Recreate management_reports table without deprecated columns
    # This handles SQLite < 3.35.0 which doesn't support DROP COLUMN
    {
        "id": "003_recreate_management_reports",
        "description": "Recreate management_reports table without one_liner and executive_summary",
        "check": lambda inspector: "management_reports" in inspector.get_table_names()
        and "executive_summary" in [c["name"] for c in inspector.get_columns("management_reports")],
        "sql": [
            # Rename old table
            "ALTER TABLE management_reports RENAME TO management_reports_old",
            # Create new table without deprecated columns
            """CREATE TABLE management_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(255) NOT NULL,
                title VARCHAR(500) NOT NULL,
                project_key VARCHAR(50),
                report_period VARCHAR(100),
                content TEXT NOT NULL,
                referenced_tickets TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )""",
            # Copy data from old table
            """INSERT INTO management_reports (id, username, title, project_key, report_period, content, referenced_tickets, created_at, updated_at)
               SELECT id, username, title, project_key, report_period, content, referenced_tickets, created_at, updated_at
               FROM management_reports_old""",
            # Drop old table
            "DROP TABLE management_reports_old",
            # Recreate indexes
            "CREATE INDEX idx_mgmt_user_created ON management_reports (username, created_at)",
            "CREATE INDEX idx_mgmt_project ON management_reports (project_key, created_at)",
        ],
        "optional": False,
    },
    # Migration 4: Add jira_components column to activity_log for auto-detection
    {
        "id": "004_add_jira_components",
        "description": "Add jira_components column to activity_log for storing Jira component info",
        "check": lambda inspector: "activity_log" in inspector.get_table_names()
        and "jira_components" not in [c["name"] for c in inspector.get_columns("activity_log")],
        "sql": [
            "ALTER TABLE activity_log ADD COLUMN jira_components VARCHAR(500)",
        ],
        "optional": False,
    },
    # Migration 5: Add detected_project_id column to activity_log for auto-detection
    {
        "id": "005_add_detected_project_id",
        "description": "Add detected_project_id column to activity_log for report consolidation",
        "check": lambda inspector: "activity_log" in inspector.get_table_names()
        and "detected_project_id" not in [c["name"] for c in inspector.get_columns("activity_log")],
        "sql": [
            "ALTER TABLE activity_log ADD COLUMN detected_project_id INTEGER REFERENCES report_projects(id)",
            "CREATE INDEX IF NOT EXISTS idx_detected_project ON activity_log (detected_project_id, timestamp)",
        ],
        "optional": False,
    },
    # Migration 6: Add visible_to_manager column to activity_log, weekly_reports, and management_reports
    # This allows users to control visibility of their data to managers
    {
        "id": "006_add_visible_to_manager",
        "description": "Add visible_to_manager column for manager visibility controls",
        "check": lambda inspector: "activity_log" in inspector.get_table_names()
        and "visible_to_manager" not in [c["name"] for c in inspector.get_columns("activity_log")],
        "sql": [
            "ALTER TABLE activity_log ADD COLUMN visible_to_manager BOOLEAN DEFAULT NULL",
            "ALTER TABLE weekly_reports ADD COLUMN visible_to_manager BOOLEAN DEFAULT NULL",
            "ALTER TABLE management_reports ADD COLUMN visible_to_manager BOOLEAN DEFAULT NULL",
        ],
        "optional": False,
    },
    # Migration 7: Create consolidated_report_snapshots table for report history
    {
        "id": "007_create_consolidated_report_snapshots",
        "description": "Create table for consolidated report snapshots/history",
        "check": lambda inspector: "consolidated_report_snapshots" not in inspector.get_table_names(),
        "sql": [
            """CREATE TABLE consolidated_report_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(id),
                created_by_id INTEGER NOT NULL REFERENCES users(id),
                report_period VARCHAR(100) NOT NULL,
                snapshot_type VARCHAR(10) NOT NULL DEFAULT 'auto',
                label VARCHAR(255),
                content TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""",
            "CREATE INDEX idx_snapshot_team_period ON consolidated_report_snapshots (team_id, report_period, created_at)",
            "CREATE INDEX idx_snapshot_created_by ON consolidated_report_snapshots (created_by_id, created_at)",
        ],
        "optional": False,
    },
    # Migration 8: Add parent_id column to report_projects for hierarchical structure
    {
        "id": "008_add_project_parent_id",
        "description": "Add parent_id column to report_projects for N-level hierarchy",
        "check": lambda inspector: "report_projects" in inspector.get_table_names()
        and "parent_id" not in [c["name"] for c in inspector.get_columns("report_projects")],
        "sql": [
            "ALTER TABLE report_projects ADD COLUMN parent_id INTEGER REFERENCES report_projects(id)",
            "CREATE INDEX IF NOT EXISTS idx_project_parent ON report_projects (parent_id)",
        ],
        "optional": False,
    },
    # Migration 9: Create github_token_configs table for multi-PAT support
    {
        "id": "009_create_github_token_configs",
        "description": "Create github_token_configs table for named GitHub token patterns",
        "check": lambda inspector: "github_token_configs" not in inspector.get_table_names(),
        "sql": [
            """CREATE TABLE github_token_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name VARCHAR(100) NOT NULL,
                patterns JSON NOT NULL,
                display_order INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                UNIQUE(user_id, name)
            )""",
            "CREATE INDEX idx_github_token_config_user ON github_token_configs (user_id, display_order)",
        ],
        "optional": False,
    },
    # Migration 10: Create personal_access_tokens table for MCP authentication
    {
        "id": "010_create_personal_access_tokens",
        "description": "Create personal_access_tokens table for PAT-based MCP auth",
        "check": lambda inspector: "personal_access_tokens" not in inspector.get_table_names(),
        "sql": [
            """CREATE TABLE personal_access_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                token_prefix VARCHAR(12) NOT NULL,
                token_hash VARCHAR(64) NOT NULL UNIQUE,
                expires_at DATETIME,
                last_used_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_revoked BOOLEAN NOT NULL DEFAULT 0
            )""",
            "CREATE INDEX idx_pat_token_hash ON personal_access_tokens (token_hash)",
            "CREATE INDEX idx_pat_user ON personal_access_tokens (user_id, created_at)",
        ],
        "optional": False,
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
        data_dir = Path(os.environ.get("GHOST_DATA_DIR", "./data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{data_dir}/ghost.db"

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
                    is_optional = migration.get("optional", False)
                    with self._engine.connect() as conn:
                        for sql in migration["sql"]:
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                                logger.info(f"  Executed: {sql[:50]}...")
                            except Exception as e:
                                error_msg = str(e).lower()
                                # Column might already exist in some edge cases
                                if "duplicate column" in error_msg:
                                    logger.warning(f"  Column already exists, skipping: {sql[:50]}...")
                                # SQLite < 3.35.0 doesn't support DROP COLUMN
                                elif is_optional and ("drop column" in sql.lower() or "no such column" in error_msg):
                                    logger.warning(f"  Optional migration step failed (likely SQLite limitation): {sql[:50]}...")
                                    logger.warning(f"  Columns will remain in database but are unused by the application")
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
