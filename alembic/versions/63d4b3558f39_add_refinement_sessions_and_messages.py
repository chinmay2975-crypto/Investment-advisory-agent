"""add refinement_sessions and refinement_messages

Revision ID: 63d4b3558f39
Revises: 81e8d545ba96
Create Date: 2026-09-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '63d4b3558f39'
down_revision = '81e8d545ba96'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('refinement_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('investor_id', sa.Integer(), nullable=False),
    sa.Column('goal_id', sa.Integer(), nullable=False),
    sa.Column('origin_recommendation_id', sa.Integer(), nullable=False),
    sa.Column('current_recommendation_id', sa.Integer(), nullable=False),
    sa.Column('active_constraints', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['current_recommendation_id'], ['recommendations.id'], ),
    sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ),
    sa.ForeignKeyConstraint(['investor_id'], ['investors.id'], ),
    sa.ForeignKeyConstraint(['origin_recommendation_id'], ['recommendations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('refinement_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.Integer(), nullable=False),
    sa.Column('turn_number', sa.Integer(), nullable=False),
    sa.Column('user_message', sa.Text(), nullable=False),
    sa.Column('resulting_recommendation_id', sa.Integer(), nullable=False),
    sa.Column('llm_provider', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['resulting_recommendation_id'], ['recommendations.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['refinement_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('refinement_messages')
    op.drop_table('refinement_sessions')
