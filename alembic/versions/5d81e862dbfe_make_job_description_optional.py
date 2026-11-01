from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5d81e862dbfe'
down_revision: Union[str, Sequence[str], None] = '8535d075e734'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('job', 'JD', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute('UPDATE job SET "JD" = \'\' WHERE "JD" IS NULL')
    op.alter_column('job', 'JD', existing_type=sa.Text(), nullable=False)
