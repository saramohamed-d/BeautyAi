"""knowledge rag

Sprint 8: embeddings (pgvector) and keyword search on knowledge chunks,
plus review metadata and full text on knowledge documents.

Revision ID: 9a41c2e7d3b5
Revises: 56b733b79e88
Create Date: 2026-09-19 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9a41c2e7d3b5'
down_revision: Union[str, None] = '56b733b79e88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The pgvector/pgvector Docker image ships the extension; this enables it in the database.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column('knowledge_documents', sa.Column('slug', sa.String(length=128), nullable=True))
    op.add_column('knowledge_documents', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('body', sa.Text(), nullable=True))
    op.add_column('knowledge_documents', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.add_column('knowledge_documents', sa.Column('reviewed_by', sa.String(length=255), nullable=True))
    op.add_column('knowledge_documents', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_knowledge_documents_slug', 'knowledge_documents', ['slug'])

    op.add_column('knowledge_chunks', sa.Column('heading', sa.String(length=512), nullable=True))
    op.add_column(
        'knowledge_chunks',
        sa.Column('language', postgresql.ENUM('ar', 'en', name='language', create_type=False), server_default='en', nullable=False),
    )
    # Existing chunks take their document's language.
    op.execute(
        "UPDATE knowledge_chunks c SET language = d.language FROM knowledge_documents d WHERE d.id = c.knowledge_document_id"
    )
    op.add_column('knowledge_chunks', sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1536), nullable=True))
    op.add_column('knowledge_chunks', sa.Column('embedding_model', sa.String(length=128), nullable=True))
    op.add_column(
        'knowledge_chunks',
        sa.Column(
            'search_vector',
            postgresql.TSVECTOR(),
            sa.Computed(
                "CASE WHEN language = 'ar' THEN to_tsvector('arabic'::regconfig, content) "
                "ELSE to_tsvector('english'::regconfig, content) END",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_knowledge_chunks_embedding_hnsw', 'knowledge_chunks', ['embedding'],
        postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'},
    )
    op.create_index('ix_knowledge_chunks_search_vector', 'knowledge_chunks', ['search_vector'], postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_search_vector', table_name='knowledge_chunks')
    op.drop_index('ix_knowledge_chunks_embedding_hnsw', table_name='knowledge_chunks')
    op.drop_column('knowledge_chunks', 'search_vector')
    op.drop_column('knowledge_chunks', 'embedding_model')
    op.drop_column('knowledge_chunks', 'embedding')
    op.drop_column('knowledge_chunks', 'language')
    op.drop_column('knowledge_chunks', 'heading')

    op.drop_constraint('uq_knowledge_documents_slug', 'knowledge_documents', type_='unique')
    op.drop_column('knowledge_documents', 'reviewed_at')
    op.drop_column('knowledge_documents', 'reviewed_by')
    op.drop_column('knowledge_documents', 'content_hash')
    op.drop_column('knowledge_documents', 'body')
    op.drop_column('knowledge_documents', 'summary')
    op.drop_column('knowledge_documents', 'slug')
    # The vector extension stays installed: other objects in the database may use it.
