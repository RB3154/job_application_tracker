"""make companies, jobs and lookup lists private to their user

Revision ID: 797444886326
Revises: c797f6d44e3b
Create Date: 2026-10-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '797444886326'
down_revision: Union[str, Sequence[str], None] = 'c797f6d44e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Rows without an owner (made before ownership existed) are given to the first user account.
# If rows exist but there are no users at all, making the column NOT NULL fails: create a user first.
FILL_OWNER = 'UPDATE {table} SET user_id = (SELECT min(id) FROM users) WHERE user_id IS NULL'

# (table, name column, old "name is unique" constraint)
LOOKUPS = [
    ('location', 'name', 'location_name_key'),
    ('work_mode', 'name', 'work_mode_name_key'),
    ('skill', 'skill_name', 'skill_skill_name_key'),
    ('education_requirement', 'education_name', 'education_requirement_education_name_key'),
    ('source', 'source_name', 'source_source_name_key'),
]

# (table, column, referenced table, referenced column): links that should go when what they link is deleted.
LINKS = [
    ('job_location', 'job_id', 'job', 'job_id'),
    ('job_location', 'loc_id', 'location', 'loc_id'),
    ('job_work_mode', 'job_id', 'job', 'job_id'),
    ('job_work_mode', 'work_mode_id', 'work_mode', 'work_mode_id'),
    ('job_skill', 'job_id', 'job', 'job_id'),
    ('job_skill', 'skill_id', 'skill', 'skill_id'),
    ('job_education', 'job_id', 'job', 'job_id'),
    ('job_education', 'education_id', 'education_requirement', 'education_id'),
    ('job_source', 'job_id', 'job', 'job_id'),
    ('job_source', 'source_id', 'source', 'source_id'),
    ('company_location', 'company_id', 'company', 'company_id'),
    ('company_location', 'loc_id', 'location', 'loc_id'),
]


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Companies and jobs: optional created_by -> required owner user_id, deleted with the account.
    for table in ('company', 'job'):
        op.drop_constraint(f'{table}_created_by_fkey', table, type_='foreignkey')
        op.alter_column(table, 'created_by', new_column_name='user_id')
        op.execute(FILL_OWNER.format(table=table))
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f'{table}_user_id_fkey', table, 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_company_user_id', 'company', ['user_id'])

    # A link only needs to be unique per user now (each user has their own copy of a job).
    op.drop_constraint('job_job_url_key', 'job', type_='unique')
    op.create_unique_constraint('uq_job_user_id_job_url', 'job', ['user_id', 'job_url'])

    # 2. Lookup lists: an owner each, and names unique per user instead of across everyone.
    for table, name_column, old_unique in LOOKUPS:
        op.add_column(table, sa.Column('user_id', sa.Integer(), nullable=True))
        op.execute(FILL_OWNER.format(table=table))
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f'{table}_user_id_fkey', table, 'users', ['user_id'], ['id'], ondelete='CASCADE')
        op.drop_constraint(old_unique, table, type_='unique')
        op.create_unique_constraint(f'uq_{table}_user_id_{name_column}', table, ['user_id', name_column])

    # 3. Link rows are deleted together with the job, company or list entry they point to,
    #    so deleting an account (which deletes those) can't be blocked by leftover links.
    for table, column, ref_table, ref_column in LINKS:
        name = f'{table}_{column}_fkey'
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, ref_table, [column], [ref_column], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema.

    Going back makes names and links unique across all users again, so it fails if two users
    have the same list entry or job link; remove the duplicates first.
    """
    for table, column, ref_table, ref_column in LINKS:
        name = f'{table}_{column}_fkey'
        op.drop_constraint(name, table, type_='foreignkey')
        op.create_foreign_key(name, table, ref_table, [column], [ref_column])

    for table, name_column, old_unique in LOOKUPS:
        op.drop_constraint(f'uq_{table}_user_id_{name_column}', table, type_='unique')
        op.create_unique_constraint(old_unique, table, [name_column])
        op.drop_constraint(f'{table}_user_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'user_id')

    op.drop_constraint('uq_job_user_id_job_url', 'job', type_='unique')
    op.create_unique_constraint('job_job_url_key', 'job', ['job_url'])

    op.drop_index('ix_company_user_id', table_name='company')
    for table in ('company', 'job'):
        op.drop_constraint(f'{table}_user_id_fkey', table, type_='foreignkey')
        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=True)
        op.alter_column(table, 'user_id', new_column_name='created_by')
        op.create_foreign_key(f'{table}_created_by_fkey', table, 'users', ['created_by'], ['id'], ondelete='SET NULL')
