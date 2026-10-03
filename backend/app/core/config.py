import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    model: str = "openai:gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    vision_model: str = "openai:gpt-4o-mini"
    openai_api_key: str = ""
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    recognition_auto_threshold: float = 0.95
    recognition_min_threshold: float = 0.80
    langsmith_api_key : str = ""
    langsmith_project : str = ""
    langsmith_auto_threshold: float = 0.95
    langsmith_min_threshold: float = 0.80

settings = Settings()

def sqlalchemy_database_url() -> str:
    url = settings.database_url
    if not url or url.startswith("postgresql+"):
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1)
    