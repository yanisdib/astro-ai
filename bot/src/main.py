import asyncio
import logging
import sys

from core.config import settings
from core.database import init_db, close_db
from ingestion.message_buffer import MessageBuffer
from providers.twitch_listener import TwitchChatListener


logger = logging.getLogger("astro")


async def main() -> None:
    """
    Bot entrypoint.

    Validates configuration, initializes the database pool and message buffer,
    then starts the TwitchChatListener. Ensures all resources are cleanly shut
    down on exit regardless of how the process terminates.
    """
    if not settings.validate_config():
        logger.error("Aborting startup due to incomplete configuration.")
        sys.exit(1)

    await init_db()
    logger.info("Database pool initialized.")

    message_buffer = MessageBuffer()
    await message_buffer.start()
    logger.info("Message buffer started.")

    bot = TwitchChatListener(message_buffer=message_buffer)

    try:
        await bot.start()
    finally:
        await message_buffer.stop()
        logger.info("Message buffer stopped.")
        await close_db()
        logger.info("Database pool closed.")


if __name__ == "__main__":
    asyncio.run(main())
