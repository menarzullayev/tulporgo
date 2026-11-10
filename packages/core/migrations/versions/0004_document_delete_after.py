"""driver documents: a rejected server copy is kept for a few days, then purged (decision 63)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11 00:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: str | Sequence[str] | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('driver_documents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delete_after', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_driver_documents_delete_after'), ['delete_after'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('driver_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_driver_documents_delete_after'))
        batch_op.drop_column('delete_after')
