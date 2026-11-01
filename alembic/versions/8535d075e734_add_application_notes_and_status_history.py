from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8535d075e734'
down_revision: Union[str, Sequence[str], None] = 'e0b41fa1a607'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('application', sa.Column('notes', sa.Text(), nullable=True))
    op.create_table(
        'application_status_change',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=30), nullable=True),
        sa.Column('to_status', sa.String(length=30), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['application.application_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_application_status_change_application_id'),
        'application_status_change',
        ['application_id'],
        unique=False,
    )
    op.execute(
        'INSERT INTO application_status_change (application_id, from_status, to_status) '
        'SELECT application_id, NULL, current_status FROM application'
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_application_status_change_application_id'), table_name='application_status_change')
    op.drop_table('application_status_change')
    op.drop_column('application', 'notes')
