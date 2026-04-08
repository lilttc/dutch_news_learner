"""Baseline revision - no DDL (historical schema from _migrate_schema).

Existing databases: ``alembic stamp baseline_001`` once so future revisions apply
in order. Do not ``upgrade`` this on a production DB expecting it to create
tables; the app migration path already ensured schema.

Revision ID: baseline_001
Revises:
Create Date: 2026-03-26

"""

revision = "baseline_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
