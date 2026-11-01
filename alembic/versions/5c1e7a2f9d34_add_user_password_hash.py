from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c1e7a2f9d34'
down_revision: Union[str, Sequence[str], None] = '2bc8d0960952'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'password_hash')
