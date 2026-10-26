import os
from functools import lru_cache
import structlog
from app.core.config import settings

log = structlog.get_logger()

class Reranker:
    def __init__(self, model=None, tokenizer=None, max_length: int = 1024):
        self.model, self.tokenizer, self.max_length = model, tokenizer, max_length
        if self.model is not None:
            self.model.eval()

    @property
    def active(self) -> bool:
        return self.model is not None

    @classmethod
    def load(cls, path: str) -> "Reranker":
        if not path or not os.path.isdir(path):
            return cls()
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            return cls(AutoModelForCausalLM.from_pretrained(path), AutoTokenizer.from_pretrained(path))
        except Exception as e:
            log.warning("reranker_load_failed", path=path, error=type(e).__name__)
            return cls()

    def _score(self, question: str, answer: str) -> float:
        import torch
        prefix = f"Q: {question}\nA: "
        n_prefix = len(self.tokenizer(prefix)["input_ids"])
        ids = self.tokenizer(prefix + answer, return_tensors="pt", truncation=True, max_length=self.max_length)
        labels = ids["input_ids"].clone()
        labels[:, :n_prefix] = -100
        if (labels != -100).sum() == 0:
            return float("-inf")
        with torch.no_grad():
            out = self.model(**ids, labels=labels)
        return float(-out.loss)              # higher = preferred

    def rank(self, question: str, candidates: list[str]) -> list[str]:
        if not self.active or len(candidates) < 2:
            return list(candidates)
        try:
            scores = [self._score(question, c) for c in candidates]
        except Exception as e:
            log.warning("reranker_score_failed", error=type(e).__name__)
            return list(candidates)
        order = sorted(range(len(candidates)), key=lambda i: -scores[i])
        return [candidates[i] for i in order]


@lru_cache(maxsize=1)
def get_reranker() -> Reranker:
    return Reranker.load(settings.reranker_path)
