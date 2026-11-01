from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7cf23241ad4'
down_revision: Union[str, Sequence[str], None] = 'fb8f1d0d8193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('uq_users_username_lower', 'users', [sa.text('lower(username)')], unique=True)
    op.create_index('uq_users_email_lower', 'users', [sa.text('lower(email)')], unique=True)
    op.drop_constraint('users_username_key', 'users', type_='unique')
    op.drop_constraint('users_email_key', 'users', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('users_email_key', 'users', ['email'])
    op.create_unique_constraint('users_username_key', 'users', ['username'])
    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_index('uq_users_username_lower', table_name='users')
