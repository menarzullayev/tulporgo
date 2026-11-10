"""trip topics: message_thread_id of the trip topic in each party's private chat

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: str | Sequence[str] | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('passenger_topic_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('driver_topic_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('trips', schema=None) as batch_op:
        batch_op.drop_column('driver_topic_id')
        batch_op.drop_column('passenger_topic_id')
