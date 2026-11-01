from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '09f2cd3da047'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('company',
    sa.Column('company_id', sa.String(length=100), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('company_site', sa.Text(), nullable=True),
    sa.Column('company_description', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('company_id')
    )
    op.create_table('education_requirement',
    sa.Column('education_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('education_name', sa.String(length=150), nullable=False),
    sa.PrimaryKeyConstraint('education_id'),
    sa.UniqueConstraint('education_name')
    )
    op.create_table('location',
    sa.Column('loc_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('loc_id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('skill',
    sa.Column('skill_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('skill_name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('skill_id'),
    sa.UniqueConstraint('skill_name')
    )
    op.create_table('source',
    sa.Column('source_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('source_name', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('source_id'),
    sa.UniqueConstraint('source_name')
    )
    op.create_table('work_mode',
    sa.Column('work_mode_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=30), nullable=False),
    sa.PrimaryKeyConstraint('work_mode_id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('company_location',
    sa.Column('company_id', sa.String(length=100), nullable=False),
    sa.Column('loc_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['company.company_id'], ),
    sa.ForeignKeyConstraint(['loc_id'], ['location.loc_id'], ),
    sa.PrimaryKeyConstraint('company_id', 'loc_id')
    )
    op.create_index('ix_company_location_loc_id', 'company_location', ['loc_id'], unique=False)
    op.create_table('job',
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=255), nullable=False),
    sa.Column('JD', sa.Text(), nullable=False),
    sa.Column('job_url', sa.Text(), nullable=False),
    sa.Column('job_posting_date', sa.Date(), nullable=False),
    sa.Column('application_deadline', sa.Date(), nullable=True),
    sa.Column('exp_min', sa.DECIMAL(precision=4, scale=1), nullable=True),
    sa.Column('exp_max', sa.DECIMAL(precision=4, scale=1), nullable=True),
    sa.Column('exp_text', sa.Text(), nullable=True),
    sa.Column('salary_text', sa.Text(), nullable=True),
    sa.Column('salary_min', sa.DECIMAL(precision=15, scale=2), nullable=True),
    sa.Column('salary_max', sa.DECIMAL(precision=15, scale=2), nullable=True),
    sa.Column('salary_currency', sa.CHAR(length=3), nullable=True),
    sa.Column('salary_period', sa.String(length=20), nullable=True),
    sa.Column('company_id', sa.String(length=100), nullable=False),
    sa.CheckConstraint('application_deadline >= job_posting_date'),
    sa.CheckConstraint('exp_max >= 0'),
    sa.CheckConstraint('exp_max >= exp_min'),
    sa.CheckConstraint('exp_min >= 0'),
    sa.CheckConstraint('salary_max >= 0'),
    sa.CheckConstraint('salary_max >= salary_min'),
    sa.CheckConstraint('salary_min >= 0'),
    sa.ForeignKeyConstraint(['company_id'], ['company.company_id'], ),
    sa.PrimaryKeyConstraint('job_id'),
    sa.UniqueConstraint('job_url')
    )
    op.create_index('ix_job_application_deadline', 'job', ['application_deadline'], unique=False)
    op.create_index('ix_job_company_id', 'job', ['company_id'], unique=False)
    op.create_index('ix_job_job_posting_date', 'job', ['job_posting_date'], unique=False)
    op.create_index('ix_job_role', 'job', ['role'], unique=False)
    op.create_table('application',
    sa.Column('application_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('date_applied', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
    sa.Column('current_status', sa.String(length=30), server_default=sa.text("'Applied'"), nullable=True),
    sa.CheckConstraint("current_status IN ('Applied', 'Screening', 'Interview', 'Rejected', 'Offer', 'Accepted', 'Withdrawn')"),
    sa.ForeignKeyConstraint(['job_id'], ['job.job_id'], ),
    sa.PrimaryKeyConstraint('application_id'),
    sa.UniqueConstraint('job_id')
    )
    op.create_index('ix_application_date_applied', 'application', ['date_applied'], unique=False)
    op.create_table('job_education',
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('education_id', sa.Integer(), nullable=False),
    sa.Column('ed_req_txt', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['education_id'], ['education_requirement.education_id'], ),
    sa.ForeignKeyConstraint(['job_id'], ['job.job_id'], ),
    sa.PrimaryKeyConstraint('job_id', 'education_id')
    )
    op.create_index('ix_job_education_education_id', 'job_education', ['education_id'], unique=False)
    op.create_table('job_location',
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('loc_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job.job_id'], ),
    sa.ForeignKeyConstraint(['loc_id'], ['location.loc_id'], ),
    sa.PrimaryKeyConstraint('job_id', 'loc_id')
    )
    op.create_index('ix_job_location_loc_id', 'job_location', ['loc_id'], unique=False)
    op.create_table('job_skill',
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('skill_id', sa.Integer(), nullable=False),
    sa.Column('skill_type', sa.String(length=20), server_default=sa.text("'required'"), nullable=True),
    sa.CheckConstraint("skill_type IN ('required', 'preferred')"),
    sa.ForeignKeyConstraint(['job_id'], ['job.job_id'], ),
    sa.ForeignKeyConstraint(['skill_id'], ['skill.skill_id'], ),
    sa.PrimaryKeyConstraint('job_id', 'skill_id')
    )
    op.create_index('ix_job_skill_skill_id', 'job_skill', ['skill_id'], unique=False)
    op.create_table('job_source',
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job.job_id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['source.source_id'], ),
    sa.PrimaryKeyConstraint('job_id', 'source_id')
    )
    op.create_index('ix_job_source_source_id', 'job_source', ['source_id'], unique=False)
    op.create_table('job_work_mode',
    sa.Column('job_id', sa.String(length=100), nullable=False),
    sa.Column('work_mode_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['job.job_id'], ),
    sa.ForeignKeyConstraint(['work_mode_id'], ['work_mode.work_mode_id'], ),
    sa.PrimaryKeyConstraint('job_id', 'work_mode_id')
    )
    op.create_index('ix_job_work_mode_work_mode_id', 'job_work_mode', ['work_mode_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_job_work_mode_work_mode_id', table_name='job_work_mode')
    op.drop_table('job_work_mode')
    op.drop_index('ix_job_source_source_id', table_name='job_source')
    op.drop_table('job_source')
    op.drop_index('ix_job_skill_skill_id', table_name='job_skill')
    op.drop_table('job_skill')
    op.drop_index('ix_job_location_loc_id', table_name='job_location')
    op.drop_table('job_location')
    op.drop_index('ix_job_education_education_id', table_name='job_education')
    op.drop_table('job_education')
    op.drop_index('ix_application_date_applied', table_name='application')
    op.drop_table('application')
    op.drop_index('ix_job_role', table_name='job')
    op.drop_index('ix_job_job_posting_date', table_name='job')
    op.drop_index('ix_job_company_id', table_name='job')
    op.drop_index('ix_job_application_deadline', table_name='job')
    op.drop_table('job')
    op.drop_index('ix_company_location_loc_id', table_name='company_location')
    op.drop_table('company_location')
    op.drop_table('work_mode')
    op.drop_table('source')
    op.drop_table('skill')
    op.drop_table('location')
    op.drop_table('education_requirement')
    op.drop_table('company')
