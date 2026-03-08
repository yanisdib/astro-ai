import os
import logging

from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR: Path = Path(__file__).resolve().parent
ENV_DIR: Path = BASE_DIR.joinpath("/")
DEV_ENV_FILEPATH: Path = ENV_DIR / ".env.dev"
load_dotenv()


class Config:
    """
    Centralized configuration management.
    Handles environment variable retrieval, path resolution, and system constants.
    """

    # Data Storage Configuration
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "astrodb")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DATABASE = os.getenv("POSTGRES_DB")
    # Twitch Configuration
    TWITCH_TOKEN: str = os.getenv("TWITCH_TOKEN", "")
    TWITCH_ACCESS_TOKEN: str = os.getenv("TWITCH_ACCESS_TOKEN", "")
    TWITCH_REFRESH_TOKEN: str = os.getenv("TWITCH_REFRESH_TOKEN", "")
    TWITCH_CHANNEL: str = os.getenv("TWITCH_CHANNEL", "")
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID", "")
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    TWITCH_CLIENT_CODE: str = os.getenv("TWITCH_CLIENT_CODE", "")
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    # Memory Buffer Configuration
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 10))  # Limit of messages by batch
    FLUSH_INTERVAL = int(os.getenv("FLUSH_INTERVAL", 60))  # Interval between flush
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    @classmethod
    def validate_config(cls) -> bool:
        """Validate the presence of critical environment variables.

        Returns:
            bool: Returns True if the configuration is complete, otherwise False.
        """
        required_vars = ["TWITCH_TOKEN", "TWITCH_CHANNEL", "OPENAI_API_KEY"]

        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            logger.error(
                f"Incomplete configuration. Missing variables: {', '.join(missing)}"
            )
            return False

        logger.info("Application's configuration successfully initialized.")
        return True


config = Config()
