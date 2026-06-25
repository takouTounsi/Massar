from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    version: Mapped[int] = mapped_column(Integer, default=1)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    display_name: Mapped[str] = mapped_column(String(120), default="Demo User")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    country: Mapped[str] = mapped_column(String(2), index=True)
    business_type: Mapped[str] = mapped_column(String(64), index=True)
    declared_stage: Mapped[str] = mapped_column(String(64), index=True)
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class ProjectProfileVersion(Base, TimestampMixin):
    __tablename__ = "project_profile_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("projects.id"), index=True)
    profile: Mapped[dict] = mapped_column(JSONB)


class JsonEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), index=True, nullable=True)
    service: Mapped[str] = mapped_column(String(80), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)


class Resource(Base, TimestampMixin):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    country: Mapped[str] = mapped_column(String(2), index=True)
    name: Mapped[str] = mapped_column(String(240))
    institution: Mapped[str] = mapped_column(String(240))
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class ResourceChunk(Base, TimestampMixin):
    __tablename__ = "resource_chunks"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    resource_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("resources.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class EvaluationRun(Base, TimestampMixin):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    average_latency: Mapped[float | None] = mapped_column(Numeric, nullable=True)


Index("ix_projects_country_stage", Project.country, Project.declared_stage)
