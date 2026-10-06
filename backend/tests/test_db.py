import pytest
from sqlalchemy import text
from app.db.session import get_engine

@pytest.mark.integration
def test_tables_and_vector_exist():
    with get_engine().connect() as c:
        assert c.execute(text("select 1 from pg_extension where extname='vector'")).first()
        assert c.execute(text("select to_regclass('public.knowledge_chunks')")).scalar()
