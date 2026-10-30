"""add wishlist application status

Revision ID: c797f6d44e3b
Revises: 5d81e862dbfe
Create Date: 2026-10-30 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c797f6d44e3b'
down_revision: Union[str, Sequence[str], None] = '5d81e862dbfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_STATUSES = "'Applied', 'Screening', 'Interview', 'Rejected', 'Offer', 'Accepted', 'Withdrawn'"
NEW_STATUSES = "'Wishlist', " + OLD_STATUSES


def upgrade() -> None:
    """Upgrade schema."""
    # A CHECK constraint can't be edited, so drop it and create it again with 'Wishlist' added.
    op.drop_constraint('application_current_status_check', 'application', type_='check')
    op.create_check_constraint(
        'application_current_status_check', 'application', f'current_status IN ({NEW_STATUSES})'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Wishlist items have to become a status the old rule allows; 'Applied' is the closest.
    op.execute("UPDATE application SET current_status = 'Applied' WHERE current_status = 'Wishlist'")
    op.drop_constraint('application_current_status_check', 'application', type_='check')
    op.create_check_constraint(
        'application_current_status_check', 'application', f'current_status IN ({OLD_STATUSES})'
    )
