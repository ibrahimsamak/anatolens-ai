from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from app.obs.cost import CostCallback

def get_chat_model(temperature: float = 0.0):
    return init_chat_model(settings.model, temperature=temperature, callbacks=[CostCallback(settings.model)])

def get_vision_model(temperature: float = 0.0):
    return init_chat_model(settings.vision_model, temperature=temperature, callbacks=[CostCallback(settings.vision_model)])

def get_embeddings():
    return OpenAIEmbeddings(model=settings.embedding_model)
