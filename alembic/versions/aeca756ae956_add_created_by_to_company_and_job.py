from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'aeca756ae956'
down_revision: Union[str, Sequence[str], None] = '9a7a9755e6a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'company',
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.add_column(
        'job',
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('job', 'created_by')
    op.drop_column('company', 'created_by')
