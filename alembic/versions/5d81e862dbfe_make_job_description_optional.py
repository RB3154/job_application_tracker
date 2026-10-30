"""make job description optional

Revision ID: 5d81e862dbfe
Revises: 8535d075e734
Create Date: 2026-10-30 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d81e862dbfe'
down_revision: Union[str, Sequence[str], None] = '8535d075e734'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Existing descriptions are kept; new jobs may leave it out.
    op.alter_column('job', 'JD', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # NOT NULL again: jobs saved without a description get an empty one first.
    op.execute('UPDATE job SET "JD" = \'\' WHERE "JD" IS NULL')
    op.alter_column('job', 'JD', existing_type=sa.Text(), nullable=False)
