import logging

from openai import OpenAI
from typing import List
from bot.src.core.config import config


logger = logging.getLogger(__name__)
OPENAI_API_KEY = config.OPENAI_API_KEY


class EmbeddingService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.model = "text-embedding-3-small"

    def get_embedding(self, text: str, model=config.EMBEDDING_MODEL):
        """
        Converts a source text into an embedding using OpenAI model.

        Args:
            text (str): source text to be converted
            model (_type_, optional): OpenAI model used for text to embedding convertion. Defaults to config.EMBEDDING_MODEL.

        Returns:
            _type_: a new embedding
        """
        if not text:
            return
        try:
            clean_text = text.replace("\n", "")
            response = self.client.embeddings.create(input=[clean_text], model=model)
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def get_embeddings_batch(self, texts: List[str], model=config.EMBEDDING_MODEL):
        if len(texts) == 0:
            return []

        try:
            response = self.client.embeddings.create(input=texts, model=model)
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise
