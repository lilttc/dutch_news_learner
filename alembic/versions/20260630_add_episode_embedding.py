"""Add Episode.embedding column for semantic search (RAG).

Postgres-only: enables the pgvector extension and adds a vector(1536) column.
No-op on SQLite (the dev fallback already has a TEXT-typed embedding column
via the ORM model's ``with_variant``, so there is nothing to migrate there).

Revision ID: 20260630_add_episode_embedding
Revises: baseline_001
Create Date: 2026-06-30

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "20260630_add_episode_embedding"
down_revision = "baseline_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.add_column("episodes", sa.Column("embedding", Vector(1536), nullable=True))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_column("episodes", "embedding")
