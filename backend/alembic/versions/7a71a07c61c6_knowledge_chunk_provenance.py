from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7a71a07c61c6'
down_revision: Union[str, Sequence[str], None] = '93715efced69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('knowledge_chunks', sa.Column('source_version', sa.String(), nullable=False, server_default=''))
    op.add_column('knowledge_chunks', sa.Column('reviewer', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('knowledge_chunks', 'reviewer')
    op.drop_column('knowledge_chunks', 'source_version')
