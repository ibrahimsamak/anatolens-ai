from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

def get_chat_model(temperature: float = 0.0):
    return init_chat_model(settings.model, temperature=temperature)

def get_vision_model(temperature: float = 0.0):
    return init_chat_model(settings.vision_model, temperature=temperature)

def get_embeddings():
    return OpenAIEmbeddings(model=settings.embedding_model)


