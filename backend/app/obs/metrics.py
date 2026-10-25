from prometheus_client import Counter, Histogram

REQUEST_LATENCY = Histogram("anatolens_request_seconds", "Request latency", ["route"])
GUARDRAIL_TRIGGERS = Counter("anatolens_guardrail_total", "Guardrail blocks", ["reason"])
RECOGNITION_CONFIDENCE = Histogram("anatolens_recognition_confidence", "Confidence", buckets=[0.1,0.2,0.3,0.35,0.4,0.45,0.5,0.6,0.8,1.0])
TOKENS_COST = Counter("anatolens_token_cost_usd", "LLM cost (USD)", ["model"])
CACHE_HITS = Counter("anatolens_cache_hits_total", "Semantic cache hits")
LLM_FALLBACKS = Counter("anatolens_llm_fallback_total", "Calls retried on the fallback model", ["primary"])
