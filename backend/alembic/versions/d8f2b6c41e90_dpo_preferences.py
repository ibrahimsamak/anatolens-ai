from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f2b6c41e90'
down_revision: Union[str, Sequence[str], None] = 'c4e1a9b27d53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dpo_preferences',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('chosen', sa.Text(), nullable=False),
    sa.Column('rejected', sa.Text(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('dpo_preferences')
