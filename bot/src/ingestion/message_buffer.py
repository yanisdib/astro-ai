import logging
import asyncio
import time

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from psycopg import OperationalError
from psycopg.errors import SerializationFailure

from core.database import pool
from core.clients import openai_client
from core.config import settings

from ingestion.queries import INSERT_DOCUMENT
from models.twitch_message import TwitchMessage
from models.stream_event import StreamEvent
from ingestion.embeddings import EmbeddingService

from utils.decorators import retry


logger = logging.getLogger("MessageBuffer")


class MessageBuffer:
    def __init__(self) -> None:
        """
        Initialize the MessageBuffer with empty queues and background task handles.

        Sets up the dual-queue structure, concurrency primitives, and a moderation
        semaphore capped at settings.BATCH_SIZE to limit concurrent OpenAI calls.
        The flush background task is not started here — call start() to begin processing.
        """
        self._embedding_service = EmbeddingService()
        self._active_message_queue: list[TwitchMessage] = []
        self._commit_message_queue: list[TwitchMessage] = []
        self._swapped_at: int = int(time.time())
        self._flush_lock = asyncio.Lock()
        self._persist_lock = asyncio.Lock()
        self._is_listening = True
        self._flush_task: asyncio.Task | None = None
        # Limits concurrent OpenAI moderation calls to avoid overwhelming the API.
        # Future: make this limit independent of BATCH_SIZE (dedicated MODERATION_CONCURRENCY setting),
        # or replace with a worker queue to decouple moderation throughput from batch size.
        self._moderation_semaphore = asyncio.Semaphore(settings.BATCH_SIZE)

    async def start(self):
        """
        Start the background periodic flush task.

        Creates an asyncio Task that calls _periodic_flush on a fixed interval.
        Must be called once after instantiation before messages are queued.
        """
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def queue_message(self, message: TwitchMessage) -> None:
        """
        Enqueues a Twitch chat message for embedding and storage.

        Appends the message to the active queue under a lock. If the queue
        reaches settings.BATCH_SIZE, a flush is triggered immediately to embed and
        persist the accumulated batch.

        Args:
            message (TwitchMessage): The incoming Twitch chat message to buffer.
        """
        async with self._moderation_semaphore:
            is_safe = await self._is_safe_message(message.content)
            if not is_safe:
                logger.debug(
                    "Message %s from user %s flagged as inappropriate",
                    message.id,
                    message.author.id,
                )
                return

        async with self._flush_lock:
            self._active_message_queue.append(message)
            if self._is_active_queue_full():
                await self._flush()

    async def stop(self) -> None:
        """
        Gracefully shuts down the MessageBuffer.

        Cancels the periodic background task and awaits its termination before
        performing a final flush of any messages remaining in the active queue.
        Ensures no data is lost on shutdown.
        """
        logger.info("Shutting down MessageBuffer core. Finalizing persistence...")
        self._is_listening = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        async with self._flush_lock:
            await self._flush()

    async def _is_safe_message(self, text: str) -> bool:
        """
        Ensures that a message is not inapproriate using OpenAI's moderation endpoint

        Args:
            text (str): chat message's content

        Returns:
            bool: true if message is compliant, otherwise false
        """
        response = await openai_client.moderations.create(input=text)
        return not response.results[0].flagged

    def _is_active_queue_full(self) -> bool:
        """Returns True if the active queue has reached or exceeded settings.BATCH_SIZE."""
        return len(self._active_message_queue) >= settings.BATCH_SIZE

    async def _periodic_flush(self, interval=settings.FLUSH_INTERVAL) -> None:
        """
        Background task that flushes the active queue on a fixed time interval.

        Runs continuously while _is_listening is True, sleeping for `interval`
        seconds between flushes. This ensures messages are persisted even when
        chat volume is low and settings.BATCH_SIZE is never reached. Cancelled cleanly
        by stop().

        Args:
            interval (int): Seconds between automatic flushes. Defaults to settings.FLUSH_INTERVAL.
        """
        while self._is_listening:
            try:
                await asyncio.sleep(interval)
                async with self._flush_lock:
                    if self._active_message_queue:
                        await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(
                    "Error occurred processing the MessageBuffer loop: %s", e
                )
                await asyncio.sleep(5)

    def _rotate_queues(self) -> None:
        """
        Promotes the active queue to the commit queue and resets the active queue.

        Assigns the current active list to _commit_message_queue (no copy needed —
        the reference is transferred), then replaces _active_message_queue with a
        fresh empty list. This lets message ingestion continue uninterrupted while
        the commit queue is being processed.
        """
        self._commit_message_queue = self._active_message_queue
        self._active_message_queue = []
        self._swapped_at = int(time.time())

    async def _flush(self) -> None:
        """
        Rotates queues, generates embeddings, and persists the batch to the database.

        Transfers the active queue to the commit queue via _rotate_queues, then
        calls EmbeddingService in a thread pool (via asyncio.to_thread) to avoid
        blocking the event loop during the synchronous OpenAI HTTP call.

        Messages are sorted by created_at before embedding to preserve chronological
        order across concurrent moderation calls.The resulting documents are then
        written to the PostgreSQL documents table.

        If any step fails, the error is logged and the commit queue is cleared
        in the finally block to prevent stale references from accumulating in memory.
        """
        if not self._active_message_queue:
            return

        self._rotate_queues()
        batch = sorted(self._commit_message_queue, key=lambda msg: msg.created_at)
        self._commit_message_queue = []

        commit_task = asyncio.create_task(self._commit_batch(batch))
        commit_task.add_done_callback(self._on_commit_done)

    def _on_commit_done(self, task: asyncio.Task) -> None:
        """
        Callback attached to each commit task to surface unhandled exceptions.

        Because _commit_batch runs as a fire-and-forget task, exceptions are not
        propagated automatically. This callback inspects the completed task and
        logs any exception so failures are not silently swallowed.

        Args:
            task (asyncio.Task): The completed commit task returned by asyncio.create_task.
        """
        if task.cancelled():
            logger.warning("Batch commit task was cancelled.")
        elif task.exception():
            logger.exception("Persist batch failed", exc_info=task.exception())

    async def _commit_batch(self, batch: list[TwitchMessage]) -> None:
        """
        Serialize commit operations by acquiring the persist lock before embedding.

        Wraps _embed_and_store_batch under _persist_lock to ensure that concurrent
        fire-and-forget commit tasks don't race each other when writing to the database.

        Args:
            batch (list[TwitchMessage]): The sorted batch of messages to embed and persist.
        """
        async with self._persist_lock:
            await self._embed_and_store_batch(batch=batch)

    @retry(
        retry_on=(
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
            InternalServerError,
        )
    )
    async def _embed_and_store_batch(self, batch: list[TwitchMessage]) -> None:
        """
        Generate embeddings for a batch of messages and persist them to the database.

        Calls the EmbeddingService to vectorize all message contents in a single
        API request, then zips each embedding with its source message to build
        the document payload. Delegates storage to _store_batch.

        Retries on transient OpenAI errors (connection, timeout, rate limit, server).

        Args:
            batch (list[TwitchMessage]): The sorted batch of messages to embed and store.

        Raises:
            APIConnectionError | APITimeoutError | RateLimitError | InternalServerError:
                Propagated after all retries are exhausted.
            ValueError: Raised by zip(strict=True) if embeddings count doesn't match batch.
        """
        embeddings = await self._embedding_service.get_embeddings_batch(
            [message.content for message in batch]
        )

        events = [
            StreamEvent.from_twitch_message(message, embedding)
            for message, embedding in zip(batch, embeddings, strict=True)
        ]

        await self._store_batch(events)

    async def _store_batch(self, events: list[StreamEvent]) -> None:
        await self._store_embeddings(events)
        # TODO: await self._persist_entities(events)

    @retry(retry_on=(OperationalError, SerializationFailure))
    async def _store_embeddings(self, events: list[StreamEvent]) -> None:
        documents = [
            {
                "message_id": event.message_id,
                "content": event.content,
                "is_shared": event.is_shared,
                "created_at": event.created_at,
                "channel_id": event.channel_id,
                "source": event.source.value,
                "author": {
                    "id": event.author.id,
                    "username": event.author.username,
                    "is_astro": event.author.is_astro,
                    "is_bot": event.author.is_bot,
                    "is_mod": event.author.is_mod,
                    "is_broadcaster": event.author.is_broadcaster,
                    "is_verified": event.author.is_verified,
                    "is_partner": event.author.is_partner,
                    "is_affiliate": event.author.is_affiliate,
                    "is_subscriber": event.author.is_subscriber,
                    "with_prime": event.author.with_prime,
                    "subscriber_tier": (
                        event.author.subscriber_tier.value
                        if event.author.subscriber_tier
                        else None
                    ),
                },
                "semantics": {
                    "embedding": event.semantics.embedding,
                    "intent_category": (
                        event.semantics.intent_category.value
                        if event.semantics.intent_category
                        else None
                    ),
                    "topics": event.semantics.topics,
                },
            }
            for event in events
        ]

        async with pool.connection() as conn:
            async with conn.cursor() as crs:
                await crs.executemany(INSERT_DOCUMENT, documents)
            await conn.commit()

        logger.info("Successfully stored %d messages into Memory.", len(documents))

    async def _persist_entities(self, events: list[StreamEvent]) -> None:
        # TODO: upsert users and channels from each StreamEvent into relational table when created.
        # Each event carries a full TwitchUser snapshot — use it to upsert user records
        # (id, username, subscriber status) and channel membership at message time.
        pass
