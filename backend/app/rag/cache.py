import json
import numpy as np
import redis
from app.llm.factory import get_embeddings
from app.obs.metrics import CACHE_HITS

class SemanticCache:
    """Embedding-similarity cache of grounded answers, namespaced by (structure_id, locale).
    Redis errors never fail a request: get misses and put/clear are skipped."""
    def __init__(self, redis_url: str, threshold: float = 0.95, max_entries: int = 50,
                 ttl_seconds: int = 7 * 24 * 3600):
        self.r = redis.Redis.from_url(redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
        self.threshold = threshold
        self.max_entries = max_entries
        self.ttl = ttl_seconds
        self.emb = get_embeddings()

    def _ns(self, structure_id: str, locale: str) -> str:
        return f"sc:{locale}:{structure_id}"

    def embed(self, question: str) -> list[float]:
        return self.emb.embed_query(question or "overview")
    
    def get(self, structure_id: str, question: str, locale: str, vec: list[float] | None = None):
        qv = np.array(vec if vec is not None else self.embed(question))
        try:
            raws = self.r.lrange(self._ns(structure_id, locale), 0, -1)
        except redis.RedisError:
            return None
        best = None
        best_sim = 0.0
        for raw in raws:
            entry = json.loads(raw)
            v = np.array(entry["vec"])
            sim = float(qv @ v / (np.linalg.norm(qv) * np.linalg.norm(v)))
            if sim > best_sim:
                best, best_sim = entry, sim
        if best and best_sim >= self.threshold:
            CACHE_HITS.inc()
            return {"answer": best["answer"], "citations": best["citations"]}
        return None

    def put(self, structure_id, question, locale, answer, citations, vec: list[float] | None = None):
        entry = {"vec": vec if vec is not None else self.embed(question), "answer": answer, "citations": citations}
        key = self._ns(structure_id, locale)
        try:
            self.r.pipeline().rpush(key, json.dumps(entry)).ltrim(key, -self.max_entries, -1).expire(key, self.ttl).execute()
        except redis.RedisError:
            pass

    def clear(self, structure_ids) -> None:
        try:
            for sid in structure_ids:
                keys = list(self.r.scan_iter(match=f"sc:*:{sid}"))
                if keys:
                    self.r.delete(*keys)
        except redis.RedisError:
            pass
