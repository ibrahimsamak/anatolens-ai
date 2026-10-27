import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")
    model: str = "openai:gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    vision_model: str = "openai:gpt-4o-mini"
    openai_api_key: str = ""
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.95
    recognition_model: str = "Qdrant/Unicom-ViT-B-32"
    recognition_auto_threshold: float = 0.45
    recognition_min_threshold: float = 0.35
    recognition_margin: float = 0.08
    recognition_exact_threshold: float = 0.95
    recognition_semantic_model: str = "Qdrant/clip-ViT-B-32"
    recognition_semantic_auto: float = 0.85
    recognition_semantic_min: float = 0.5
    langsmith_api_key : str = ""
    langsmith_project : str = ""
    langsmith_auto_threshold: float = 0.95
    langsmith_min_threshold: float = 0.80
    mlflow_tracing: bool = False
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "anatolens-tutor"
    judge_backend: Literal["llm", "jev"] = "llm"
    judge_threshold: float = 0.5
    jev_url: str = ""
    jev_api_key: str = ""
    jev_timeout: float = 2.0
    reranker_path: str = ""
    tutor_candidates: int = 3
    tutor_candidate_temperature: float = 0.7
    dpo_collect: bool = False
    knowledge_source: Literal["direct", "mcp"] = "direct"
    tutor_mode: Literal["pipeline", "agent"] = "pipeline"
    agent_max_steps: int = 6
    jwt_secret: str = "dev-only-jwt-secret-change-me-in-production"
    access_token_ttl: int = 3600
    refresh_token_ttl: int = 7 * 24 * 3600
settings = Settings()

def sqlalchemy_database_url() -> str:
    url = settings.database_url
    if not url or url.startswith("postgresql+"):
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1)
    