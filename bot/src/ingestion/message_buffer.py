import os
import logging
import asyncio

from typing import List

from bot.src.models.chat_message import ChatMessage


LOGGER = logging.getLogger(__name__)
LISTENER_INTERVAL_MS: int = 36000
BATCH_LIMIT: int = 10


class MessageBuffer:
    def __init__(self) -> None:
        self._active_message_queue: List[ChatMessage] = []
        self._commit_message_queue: List[ChatMessage] = []
        self._lock = asyncio.Lock()
        self._is_listening = True
        pass

    def read_messages(self) -> None:
        return

    def store_message(self, message: ChatMessage) -> bool:
        return True

    def _is_active_queue_full(self) -> bool:
        return len(self._active_message_queue) >= BATCH_LIMIT
