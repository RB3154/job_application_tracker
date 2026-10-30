"""add created_by to company and job

Revision ID: aeca756ae956
Revises: 9a7a9755e6a4
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aeca756ae956'
down_revision: Union[str, Sequence[str], None] = '9a7a9755e6a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable, so existing companies and jobs (which have no known creator) get NULL.
    op.add_column(
        'company',
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.add_column(
        'job',
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('job', 'created_by')
    op.drop_column('company', 'created_by')
