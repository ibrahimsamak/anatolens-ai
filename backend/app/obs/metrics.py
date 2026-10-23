from prometheus_client import Counter, Histogram

REQUEST_LATENCY = Histogram("anatolens_request_seconds", "Request latency", ["route"])
GUARDRAIL_TRIGGERS = Counter("anatolens_guardrail_total", "Guardrail blocks", ["reason"])
RECOGNITION_CONFIDENCE = Histogram("anatolens_recognition_confidence", "Confidence", buckets=[0.5,0.6,0.7,0.8,0.9,0.95,1.0])
TOKENS_COST = Counter("anatolens_token_cost_usd", "LLM cost (USD)", ["model"])
CACHE_HITS = Counter("anatolens_cache_hits_total", "Semantic cache hits")
