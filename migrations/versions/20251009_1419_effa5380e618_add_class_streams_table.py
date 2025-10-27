"""add class streams table

Revision ID: effa5380e618
Revises: 86ed3eb79381
Create Date: 2025-10-09 14:19:39.122637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'effa5380e618'
down_revision: Union[str, Sequence[str], None] = '86ed3eb79381'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Create class_streams table
    op.create_table(
        'class_streams',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('class_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('class_id', 'name', name='uq_stream_per_class')
    )
    
    # Create indexes
    op.create_index('ix_class_streams_school_id', 'class_streams', ['school_id'])
    op.create_index('ix_class_streams_class_id', 'class_streams', ['class_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_class_streams_class_id', table_name='class_streams')
    op.drop_index('ix_class_streams_school_id', table_name='class_streams')
    
    # Drop table
    op.drop_table('class_streams')