"""Add parfumo_url column to fragrances table

Revision ID: 6ff7e38b0060
Revises: 001
Create Date: 2025-12-30 15:03:14.929391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ff7e38b0060'
down_revision: Union[str, Sequence[str], None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parfumo_url column to fragrances table."""
    op.add_column(
        'fragrances',
        sa.Column('parfumo_url', sa.String(500), nullable=True)
    )


def downgrade() -> None:
    """Remove parfumo_url column from fragrances table."""
    op.drop_column('fragrances', 'parfumo_url')
