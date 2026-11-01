from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2bc8d0960952'
down_revision: Union[str, Sequence[str], None] = '09f2cd3da047'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )

    op.execute("DELETE FROM application")

    op.add_column('application', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key(
        'application_user_id_fkey', 'application', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )
    op.drop_constraint('application_job_id_key', 'application', type_='unique')
    op.create_unique_constraint('application_user_id_job_id_key', 'application', ['user_id', 'job_id'])

    op.execute("CREATE SEQUENCE application_application_id_seq OWNED BY application.application_id")
    op.execute(
        "ALTER TABLE application ALTER COLUMN application_id "
        "SET DEFAULT nextval('application_application_id_seq')"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE application ALTER COLUMN application_id DROP DEFAULT")
    op.execute("DROP SEQUENCE application_application_id_seq")

    op.drop_constraint('application_user_id_job_id_key', 'application', type_='unique')
    op.create_unique_constraint('application_job_id_key', 'application', ['job_id'])
    op.drop_constraint('application_user_id_fkey', 'application', type_='foreignkey')
    op.drop_column('application', 'user_id')
    op.drop_table('users')
