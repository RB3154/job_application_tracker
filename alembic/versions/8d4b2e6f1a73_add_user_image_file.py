from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8d4b2e6f1a73'
down_revision: Union[str, Sequence[str], None] = '5c1e7a2f9d34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('image_file', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'image_file')
