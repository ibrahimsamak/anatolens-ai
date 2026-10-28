from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9c3e7f15b28'
down_revision: Union[str, Sequence[str], None] = 'f5b2d8e61a07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('edge_proposals',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('subject_id', sa.String(), nullable=False),
    sa.Column('predicate', sa.String(), nullable=False),
    sa.Column('object_id', sa.String(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('conflict', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_edge_proposals_lesson_id'), 'edge_proposals', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_edge_proposals_status'), 'edge_proposals', ['status'], unique=False)
    op.create_table('mesh_candidates',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('lesson_id', sa.String(), nullable=False),
    sa.Column('glb_path', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('reason', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mesh_candidates_lesson_id'), 'mesh_candidates', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_mesh_candidates_status'), 'mesh_candidates', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_mesh_candidates_status'), table_name='mesh_candidates')
    op.drop_index(op.f('ix_mesh_candidates_lesson_id'), table_name='mesh_candidates')
    op.drop_table('mesh_candidates')
    op.drop_index(op.f('ix_edge_proposals_status'), table_name='edge_proposals')
    op.drop_index(op.f('ix_edge_proposals_lesson_id'), table_name='edge_proposals')
    op.drop_table('edge_proposals')
