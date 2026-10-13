import re
from sqlalchemy import select
from rank_bm25 import BM25Okapi

from app.models.content import KnowledgeChunk
from app.llm.factory import get_embeddings

def retrieve_chunks(structure_ids: list[str], query: str, locale:str, db, k: int = 5):
    qv = get_embeddings().embed_query(query)
    stmt = (select(KnowledgeChunk)
           .where(KnowledgeChunk.review_status == "APPROVED",
                  KnowledgeChunk.locale == locale,
                  KnowledgeChunk.structure_id.in_(structure_ids))
            .order_by(KnowledgeChunk.embedding.cosine_distance(qv))
            .limit(k))
    
    return db.execute(stmt).scalars().all()

def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())

def _approve_chunks(structure_ids, locale, db):
    return db.execute(select(KnowledgeChunk).where(
        KnowledgeChunk.review_status == "APPROVED",
        KnowledgeChunk.locale == locale,
        KnowledgeChunk.structure_id.in_(structure_ids)
    )).scalars().all()

def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores

def retrieve_chunks_hybrid(structure_ids, query, locale, db, k: int = 5):
    chunks = _approve_chunks(structure_ids, locale, db)
    if not chunks:
        return []
    by_id = {c.id: c for c in chunks}
    qv = get_embeddings().embed_query(query)

    dense = db.execute(select(KnowledgeChunk.id).where(KnowledgeChunk.id.in_(by_id.keys()))
                       .order_by(KnowledgeChunk.embedding.cosine_distance(qv)).limit(k * 2)).scalars().all()

    ids = list(by_id)
    bm25 = BM25Okapi([_tokens(by_id[cid].text) for cid in ids])
    bm25_scores = bm25.get_scores(_tokens(query))
    order = [cid for _, cid in sorted(zip(bm25_scores, ids), reverse=True)][:k * 2]

    fused = _rrf([list(dense), order])
    top = sorted(fused, key=fused.get, reverse=True)[:k]
    return [by_id[cid] for cid in top]
