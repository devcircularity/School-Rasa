"""Add boarding_type and gender_type to schools

Revision ID: 82044c16df04
Revises: effa5380e618
Create Date: 2025-10-10 14:58:32.829017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '82044c16df04'
down_revision: Union[str, Sequence[str], None] = 'effa5380e618'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add columns with defaults
    op.add_column('schools', sa.Column('boarding_type', sa.String(10), nullable=False, server_default='DAY'))
    op.add_column('schools', sa.Column('gender_type', sa.String(10), nullable=False, server_default='MIXED'))

def downgrade():
    op.drop_column('schools', 'gender_type')
    op.drop_column('schools', 'boarding_type')