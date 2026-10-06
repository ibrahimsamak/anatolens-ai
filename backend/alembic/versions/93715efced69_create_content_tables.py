from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


revision: str = '93715efced69'
down_revision: Union[str, Sequence[str], None] = '380fe42e3b0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('lessons',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('system', sa.String(), nullable=False),
    sa.Column('model_url', sa.String(), nullable=False),
    sa.Column('ios_model_url', sa.String(), nullable=True),
    sa.Column('review_status', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('scan_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('knowledge_chunks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('structure_id', sa.String(), nullable=True),
    sa.Column('locale', sa.String(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('review_status', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=False),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('phash', sa.String(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=512), nullable=False),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('structures',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('mesh_name', sa.String(), nullable=True),
    sa.Column('display_name_en', sa.String(), nullable=False),
    sa.Column('display_name_ar', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('structures')
    op.drop_table('pages')
    op.drop_table('knowledge_chunks')
    op.drop_table('scan_sessions')
    op.drop_table('lessons')
