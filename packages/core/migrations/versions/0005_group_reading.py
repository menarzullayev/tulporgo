"""reading taxi groups: driver filters, group readers, feed cards, delivery chat, consent version (decision 73)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11 19:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: str | Sequence[str] | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'driver_filters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('routes', sa.JSON(), nullable=False),
        sa.Column('time_from', sa.String(length=5), nullable=True),
        sa.Column('time_to', sa.String(length=5), nullable=True),
        sa.Column('include_asap', sa.Boolean(), nullable=False),
        sa.Column('include_tomorrow', sa.Boolean(), nullable=False),
        sa.Column('weekdays', sa.JSON(), nullable=False),
        sa.Column('seats_min', sa.Integer(), nullable=True),
        sa.Column('seats_max', sa.Integer(), nullable=True),
        sa.Column('kinds', sa.JSON(), nullable=False),
        sa.Column('group_chat_ids', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('driver_filters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_driver_filters_driver_id'), ['driver_id'], unique=False)
    op.create_table(
        'group_readers',
        sa.Column('chat_id', sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['userbot_accounts.id'], ),
        sa.PrimaryKeyConstraint('chat_id'),
    )
    with op.batch_alter_table('group_readers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_group_readers_account_id'), ['account_id'], unique=False)
    op.create_table(
        'feed_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('delete_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('feed_cards', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_feed_cards_delete_at'), ['delete_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_feed_cards_driver_id'), ['driver_id'], unique=False)
    with op.batch_alter_table('drivers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delivery_chat_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('feed_paused', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('userbot_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('consent_version', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('userbot_accounts', schema=None) as batch_op:
        batch_op.drop_column('consent_version')
    with op.batch_alter_table('drivers', schema=None) as batch_op:
        batch_op.drop_column('feed_paused')
        batch_op.drop_column('delivery_chat_id')
    with op.batch_alter_table('feed_cards', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_feed_cards_driver_id'))
        batch_op.drop_index(batch_op.f('ix_feed_cards_delete_at'))
    op.drop_table('feed_cards')
    with op.batch_alter_table('group_readers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_group_readers_account_id'))
    op.drop_table('group_readers')
    with op.batch_alter_table('driver_filters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_driver_filters_driver_id'))
    op.drop_table('driver_filters')
