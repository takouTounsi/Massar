from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("business_type", sa.String(length=64), nullable=False),
        sa.Column("declared_stage", sa.String(length=64), nullable=False),
        sa.Column("profile", postgresql.JSONB(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("ix_projects_country_stage", "projects", ["country", "declared_stage"])
    op.create_index("ix_projects_id", "projects", ["id"])

    json_tables = [
        "project_profile_versions",
        "intake_sessions",
        "questions",
        "answers",
        "diagnoses",
        "maturity_predictions",
        "score_runs",
        "score_components",
        "blockers",
        "eligibility_results",
        "roadmaps",
        "roadmap_actions",
        "progress_events",
        "model_versions",
        "rule_versions",
        "evaluation_runs",
    ]
    for table_name in json_tables:
        op.create_table(
            table_name,
            sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
            sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True, index=True),
            sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )

    op.create_table(
        "resources",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("institution", sa.String(length=240), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_resources_country", "resources", ["country"])
    op.execute(
        """
        CREATE TABLE resource_chunks (
            id text PRIMARY KEY,
            resource_id uuid REFERENCES resources(id),
            content text NOT NULL,
            metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
            embedding vector(32),
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            version integer NOT NULL DEFAULT 1
        )
        """
    )
    op.execute("CREATE INDEX ix_resource_chunks_embedding ON resource_chunks USING ivfflat (embedding vector_cosine_ops)")
    op.create_index("ix_resource_chunks_resource_id", "resource_chunks", ["resource_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("service", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    for table_name in [
        "audit_events",
        "resource_chunks",
        "resources",
        "evaluation_runs",
        "rule_versions",
        "model_versions",
        "progress_events",
        "roadmap_actions",
        "roadmaps",
        "eligibility_results",
        "blockers",
        "score_components",
        "score_runs",
        "maturity_predictions",
        "diagnoses",
        "answers",
        "questions",
        "intake_sessions",
        "project_profile_versions",
        "projects",
        "users",
    ]:
        op.drop_table(table_name)
