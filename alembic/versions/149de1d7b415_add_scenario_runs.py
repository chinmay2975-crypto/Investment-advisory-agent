"""add scenario_runs

Revision ID: 149de1d7b415
Revises: 63d4b3558f39
Create Date: 2026-09-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '149de1d7b415'
down_revision = '63d4b3558f39'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('scenario_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('investor_id', sa.Integer(), nullable=False),
    sa.Column('goal_id', sa.Integer(), nullable=False),
    sa.Column('conservative_recommendation_id', sa.Integer(), nullable=False),
    sa.Column('balanced_recommendation_id', sa.Integer(), nullable=False),
    sa.Column('aggressive_recommendation_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['aggressive_recommendation_id'], ['recommendations.id'], ),
    sa.ForeignKeyConstraint(['balanced_recommendation_id'], ['recommendations.id'], ),
    sa.ForeignKeyConstraint(['conservative_recommendation_id'], ['recommendations.id'], ),
    sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ),
    sa.ForeignKeyConstraint(['investor_id'], ['investors.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('scenario_runs')
