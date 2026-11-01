from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fb8f1d0d8193'
down_revision: Union[str, Sequence[str], None] = 'aeca756ae956'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'token_version')
