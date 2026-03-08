import logging

from openai import OpenAI
from core.config import config


logger = logging.getLogger(__name__)
OPENAI_API_KEY = config.OPENAI_API_KEY


class EmbeddingService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def get_embedding(
        self, text: str, model=config.EMBEDDING_MODEL
    ) -> list[float] | None:
        """
        Converts a single text string into a vector embedding using OpenAI.

        Newlines are stripped before encoding to avoid tokenization artifacts.

        Args:
            text (str): The source text to embed.
            model (str): OpenAI embedding model to use. Defaults to config.EMBEDDING_MODEL.

        Returns:
            list[float] | None: The embedding vector, or None if text is empty.

        Raises:
            openai.OpenAIError: If the API call fails.
        """
        if not text:
            return None
        try:
            clean_text = text.replace("\n", "")
            response = self.client.embeddings.create(input=[clean_text], model=model)
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def get_embeddings_batch(
        self, texts: list[str], model=config.EMBEDDING_MODEL
    ) -> list[list[float]]:
        """
        Converts a list of texts into embedding vectors in a single API call.

        Newlines are stripped from each text before encoding. The returned list
        preserves the same order as the input, making it safe to zip with the
        original messages.

        Args:
            texts (list[str]): The source texts to embed.
            model (str): OpenAI embedding model to use. Defaults to config.EMBEDDING_MODEL.

        Returns:
            list[list[float]]: A list of embedding vectors, one per input text.
                Returns an empty list if texts is empty.

        Raises:
            openai.OpenAIError: If the API call fails.
        """
        if len(texts) == 0:
            return []

        try:
            clean_texts = [text.replace("\n", "") for text in texts]
            response = self.client.embeddings.create(input=clean_texts, model=model)
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise
