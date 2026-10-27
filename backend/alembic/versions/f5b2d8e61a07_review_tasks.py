from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5b2d8e61a07'
down_revision: Union[str, Sequence[str], None] = 'e3a7c5d19f42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('review_tasks',
    sa.Column('thread_id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('structure_id', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('draft_text', sa.Text(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('reviewer', sa.String(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('thread_id')
    )
    op.create_index(op.f('ix_review_tasks_lesson_id'), 'review_tasks', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_review_tasks_status'), 'review_tasks', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_review_tasks_status'), table_name='review_tasks')
    op.drop_index(op.f('ix_review_tasks_lesson_id'), table_name='review_tasks')
    op.drop_table('review_tasks')
