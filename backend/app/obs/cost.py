from pathlib import Path
import yaml
from langchain_core.callbacks import BaseCallbackHandler

_PRICING = yaml.safe_load(open(Path(__file__).resolve().parents[2] / "eval" / "config.yaml"))["cost_per_1k"]

def track_cost(model: str, in_tok: int, out_tok: int) -> float:
    p = _PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost = (in_tok/1000)*p["input"] + (out_tok/1000)*p["output"]
    from app.obs.metrics import TOKENS_COST
    TOKENS_COST.labels(model=model).inc(cost)
    return cost

class CostCallback(BaseCallbackHandler):
    def __init__(self, model: str): self.model = model

    def on_llm_end(self, response, **kwargs) -> None:
        for gens in response.generations:
            for g in gens:
                usage = getattr(getattr(g, "message", None), "usage_metadata", None)
                if usage:
                    track_cost(self.model, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
