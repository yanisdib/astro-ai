from openai import AsyncOpenAI
from config import settings


openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
