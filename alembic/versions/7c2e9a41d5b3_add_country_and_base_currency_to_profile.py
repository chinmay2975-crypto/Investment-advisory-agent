"""add country and base_currency to investor_profile

Revision ID: 7c2e9a41d5b3
Revises: 149de1d7b415
Create Date: 2026-10-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c2e9a41d5b3'
down_revision = '149de1d7b415'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('investor_profile', sa.Column('country', sa.String(), nullable=True))
    op.add_column('investor_profile', sa.Column('base_currency', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('investor_profile', 'base_currency')
    op.drop_column('investor_profile', 'country')
