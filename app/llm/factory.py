from functools import lru_cache

from app.config import settings
from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient
from app.llm.router import LLMRouter


@lru_cache
def get_router() -> LLMRouter:
    return LLMRouter(
        [
            GeminiClient(api_key=settings.gemini_api_key),
            GroqClient(api_key=settings.groq_api_key),
        ]
    )
