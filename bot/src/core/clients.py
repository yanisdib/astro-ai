from openai import AsyncOpenAI
from core.config import settings


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
