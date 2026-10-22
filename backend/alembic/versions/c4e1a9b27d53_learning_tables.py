from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4e1a9b27d53'
down_revision: Union[str, Sequence[str], None] = '7a71a07c61c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('quiz_questions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('structure_id', sa.String(), nullable=False),
    sa.Column('difficulty', sa.String(), nullable=False),
    sa.Column('prompt', sa.String(), nullable=False),
    sa.Column('correct', sa.String(), nullable=False),
    sa.Column('choices', sa.JSON(), nullable=False),
    sa.Column('review_status', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('attempts',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('question_id', sa.String(), nullable=False),
    sa.Column('correct', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['quiz_questions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('progress',
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('structure_id', sa.String(), nullable=False),
    sa.Column('mastery', sa.Float(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('user_id', 'structure_id')
    )
    op.create_table('bandit_events',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('context_json', sa.JSON(), nullable=False),
    sa.Column('reward', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bandit_events_user_id', 'bandit_events', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_bandit_events_user_id', table_name='bandit_events')
    op.drop_table('bandit_events')
    op.drop_table('progress')
    op.drop_table('attempts')
    op.drop_table('quiz_questions')
