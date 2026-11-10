"""driver documents: encrypted server copy of licence and tech passport (decision 57)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10 23:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: str | Sequence[str] | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'driver_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('content_type', sa.String(length=64), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('data_encrypted', sa.LargeBinary().with_variant(mysql.LONGBLOB(), 'mysql'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], name=op.f('fk_driver_documents_driver_id_drivers')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_driver_documents')),
        sa.UniqueConstraint('driver_id', 'kind', name=op.f('uq_driver_documents_driver_id')),
    )
    with op.batch_alter_table('driver_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_driver_documents_driver_id'), ['driver_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('driver_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_driver_documents_driver_id'))
    op.drop_table('driver_documents')
