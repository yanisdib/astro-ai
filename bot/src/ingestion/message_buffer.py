import logging
import asyncio
import time

from queries import INSERT_DOCUMENT
from models.chat_message import ChatMessage
from core.database import pool
from core.clients import openai_client
from core.config import settings
from embeddings import EmbeddingService


logger = logging.getLogger(__name__)


class MessageBuffer:
    def __init__(self) -> None:
        self._embedding_service = EmbeddingService()
        self._active_message_queue: list[ChatMessage] = []
        self._commit_message_queue: list[ChatMessage] = []
        self._swapped_at: int = int(time.time())
        self._flush_lock = asyncio.Lock()
        self._persist_lock = asyncio.Lock()
        self._is_listening = True
        self._flush_task: asyncio.Task | None = None
        self._moderation_semaphore = asyncio.Semaphore(settings.BATCH_SIZE)

    async def start(self):
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def queue_message(self, message: ChatMessage) -> None:
        """
        Enqueues a Twitch chat message for embedding and storage.

        Appends the message to the active queue under a lock. If the queue
        reaches settings.BATCH_SIZE, a flush is triggered immediately to embed and
        persist the accumulated batch.

        Args:
            message (ChatMessage): The incoming Twitch chat message to buffer.
        """
        if not message:
            logger.debug("Cannot proceed with nonexistent message")
            return

        async with self._moderation_semaphore:
            is_safe = await self._is_safe_message(message.content)
            if not is_safe:
                logger.info(
                    "Message %s from user %s flagged as inappropriate",
                    message.id,
                    message.user_id,
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
                    f"Error occurred processing the MessageBuffer loop: {e}"
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
        if task.exception():
            logger.exception("Persist batch failed", exc_info=task.exception())

    async def _store_batch(self, documents: list[dict]) -> None:
        """
        Persists a batch of embedded Twitch chat messages to the documents table for RAG retrieval.

        Each document contains the raw message content alongside its embedding vector,
        enabling similarity search at query time. Commits the full batch atomically —
        either all rows are written or none are.

        Args:
            documents (list[dict]): Documents to insert, each with the following keys:
                - content (str): Raw Twitch chat message text.
                - embedding (list[float]): Vector representation from EmbeddingService.
                - channel_id (str): Twitch channel the message originated from.
                - source_type (str): Origin platform identifier (e.g. "twitch").
                - created_at (int): Unix timestamp of the original message.
        """
        try:
            async with pool.connection() as conn:
                async with conn.cursor() as crs:
                    await crs.executemany(INSERT_DOCUMENT, documents)
                await conn.commit()
            logger.info(f"Successfully refined {len(documents)} messages into Memory.")
        except Exception as e:
            logger.exception(f"Error while storing the batch: {e}")
            # Implement retry with jitter decorator

    async def _commit_batch(self, batch: list[ChatMessage]) -> None:
        async with self._persist_lock:
            await self._embed_and_store_batch(batch=batch)

    # TODO: add retry decorator here
    async def _embed_and_store_batch(self, batch: list[ChatMessage]) -> None:
        embeddings = await self._embedding_service.get_embeddings_batch(
            [message.content for message in batch]
        )
        documents = [
            {
                "content": message.content,
                "embedding": embedding,
                "channel_id": message.extra_metadata.get("channel_id"),
                "source_type": message.extra_metadata.get("source_type"),
                "created_at": message.created_at,
            }
            for message, embedding in zip(batch, embeddings, strict=True)
        ]

        await self._store_batch(documents=documents)
