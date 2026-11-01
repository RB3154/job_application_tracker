from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a7a9755e6a4'
down_revision: Union[str, Sequence[str], None] = 'a3f9c1d7e520'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application', sa.Column('interview_rounds', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('application', 'interview_rounds')
