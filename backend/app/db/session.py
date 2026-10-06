from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import sqlalchemy_database_url


def get_engine():
    return create_engine(sqlalchemy_database_url(),pool_pre_ping=True)

SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
