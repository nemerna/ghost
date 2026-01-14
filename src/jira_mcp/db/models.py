"""SQLAlchemy models for activity tracking and weekly reports."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text, Index
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class ActionType(str, enum.Enum):
    """Types of actions that can be logged."""
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    COMMENT = "comment"
    TRANSITION = "transition"
    LINK = "link"
    OTHER = "other"


class ActivityLog(Base):
    """Log of Jira ticket interactions for activity tracking."""
    
    __tablename__ = "activity_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User info (from Jira auth)
    username = Column(String(255), nullable=False, index=True)
    
    # Ticket info
    ticket_key = Column(String(50), nullable=False, index=True)
    ticket_summary = Column(String(500), nullable=True)
    project_key = Column(String(50), nullable=True, index=True)
    
    # Action info
    action_type = Column(Enum(ActionType), nullable=False, default=ActionType.OTHER)
    action_details = Column(Text, nullable=True)  # JSON string with additional context
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Indexes for weekly report queries
    __table_args__ = (
        Index("idx_user_timestamp", "username", "timestamp"),
        Index("idx_user_project_timestamp", "username", "project_key", "timestamp"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "ticket_key": self.ticket_key,
            "ticket_summary": self.ticket_summary,
            "project_key": self.project_key,
            "action_type": self.action_type.value if self.action_type else None,
            "action_details": self.action_details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class WeeklyReport(Base):
    """Stored weekly reports for users."""
    
    __tablename__ = "weekly_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User info
    username = Column(String(255), nullable=False, index=True)
    
    # Report period
    week_start = Column(DateTime, nullable=False, index=True)
    week_end = Column(DateTime, nullable=False)
    
    # Report content
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=False)  # Executive summary
    content = Column(Text, nullable=False)  # Full report content (Markdown)
    
    # Metadata
    tickets_count = Column(Integer, nullable=False, default=0)
    projects = Column(String(500), nullable=True)  # Comma-separated project keys
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_user_week", "username", "week_start"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "week_start": self.week_start.isoformat() if self.week_start else None,
            "week_end": self.week_end.isoformat() if self.week_end else None,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "tickets_count": self.tickets_count,
            "projects": self.projects.split(",") if self.projects else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ManagementReport(Base):
    """Management-level project progress reports (AI-generated content)."""
    
    __tablename__ = "management_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Author info
    username = Column(String(255), nullable=False, index=True)
    
    # Report metadata
    title = Column(String(500), nullable=False)
    project_key = Column(String(50), nullable=True, index=True)  # Optional project focus
    report_period = Column(String(100), nullable=True)  # e.g., "Week 3, January 2026" or "Sprint 42"
    
    # Report content (AI-generated Markdown) - CONCISE
    one_liner = Column(String(200), nullable=True)  # Single sentence elevator pitch (max 15 words)
    executive_summary = Column(Text, nullable=False)  # 2-3 sentence high-level summary
    content = Column(Text, nullable=False)  # Full Markdown report (aim for <500 words)
    
    # Referenced Jira tickets (comma-separated keys for linking)
    referenced_tickets = Column(Text, nullable=True)  # e.g., "APPENG-4112,APPENG-4256"
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index("idx_mgmt_user_created", "username", "created_at"),
        Index("idx_mgmt_project", "project_key", "created_at"),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "username": self.username,
            "title": self.title,
            "project_key": self.project_key,
            "report_period": self.report_period,
            "one_liner": self.one_liner,
            "executive_summary": self.executive_summary,
            "content": self.content,
            "referenced_tickets": self.referenced_tickets.split(",") if self.referenced_tickets else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
