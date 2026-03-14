import asyncio
import logging

from functools import wraps
from random import random
from core.config import settings


DEFAULT_MAX_RETRIES = 3

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


def retry(retries=DEFAULT_MAX_RETRIES, retry_on=(Exception,)):
    """
    Async decorator that retries a coroutine on specified transient exceptions.

    Uses exponential backoff with jitter between attempts. Exceptions not listed
    in retry_on are treated as unrecoverable and re-raised immediately without retry.

    Args:
        retries (int): Maximum number of retry attempts. Defaults to DEFAULT_MAX_RETRIES.
        retry_on (tuple[type[Exception], ...]): Exception types that should trigger a retry.
            All other exceptions fail fast. Defaults to (Exception,).

    Returns:
        The decorated coroutine function.

    Raises:
        The last caught retry_on exception once retries are exhausted.
        Any exception not in retry_on, immediately on first occurrence.

    Example:
        @retry(retries=5, retry_on=(RateLimitError, APITimeoutError))
        async def call_api(): ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            count: int = 0

            while True:
                try:
                    return await func(*args, **kwargs)
                except retry_on as e:
                    count += 1
                    if count > retries:
                        logger.info("Maximum retries reached. Last error: %s", e)
                        raise e

                    delay = (2**count) + random()  # exponential backoff + jitter
                    logger.debug(f"Caught expected error: {type(e).__name__}")
                    logger.info("Retrying in %s seconds...", delay)
                    await asyncio.sleep(delay)
                except Exception as e:
                    # This catches unexpected errors (like ValueError) and fails fast
                    logger.debug("Unrecoverable error: %s", e)
                    raise e

        return wrapper

    return decorator
