import os
import logging

from pathlib import Path
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)-20s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("config")

BASE_DIR: Path = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent.parent / "env" / ".env.dev")


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
    TWITCH_BOT_ID: str = os.getenv("TWITCH_BOT_ID", "")
    TWITCH_CHANNEL: str = os.getenv("TWITCH_CHANNEL", "")
    TWITCH_CLIENT_ID: str = os.getenv("TWITCH_CLIENT_ID", "")
    TWITCH_CLIENT_SECRET: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    # Memory Buffer Configuration
    BATCH_SIZE = int(os.getenv("BATCH_SIZE", 10))  # Limit of messages by batch
    FLUSH_INTERVAL = int(os.getenv("FLUSH_INTERVAL", 60))  # Interval between flush
    # Bot configuration
    BOT_COMMAND = "!astro"
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    @classmethod
    def validate_config(cls) -> bool:
        """Validate the presence of critical environment variables.

        Returns:
            bool: Returns True if the configuration is complete, otherwise False.
        """
        required_vars = [
            "TWITCH_BOT_ID",
            "TWITCH_CLIENT_ID",
            "TWITCH_CHANNEL",
            "OPENAI_API_KEY",
        ]

        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            logger.error(
                f"Incomplete configuration. Missing variables: {', '.join(missing)}"
            )
            return False

        logger.info("Application's configuration successfully initialized.")
        return True


settings = Config()
