from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from models.twitch_user import SubscriberTier

if TYPE_CHECKING:
    from models.twitch_message import TwitchMessage


class IntentCategory(Enum):
    """Classifies the conversational intent of a chat message."""

    COMMAND = "command"
    QUESTION = "question"
    CHATTING = "chatting"
    REACTION = "reaction"


class EventSource(Enum):
    """Identifies the streaming platform that originated a chat event."""

    TWITCH = "twitch"
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


@dataclass(frozen=True)
class StreamEvent:
    """
    Core Data Transfer Object representing a single immutable event message.
    """

    # Core data
    message_id: str
    content: str
    user_id: str
    username: str
    is_host: bool
    is_bot: bool
    is_mod: bool
    is_verified: bool
    is_shared: bool
    created_at: int

    # Analytics (Metadata)
    channel_id: str
    source: EventSource

    # Chatter status at message time
    is_subscribed: bool = False
    subscriber_tier: Optional[SubscriberTier] = None

    # Semantic Intelligence
    embedding: list[float] = field(default_factory=list)
    intent_category: Optional[IntentCategory] = IntentCategory.CHATTING
    topics: list[str] = field(default_factory=list)

    @classmethod
    def from_twitch_message(cls, message: TwitchMessage, embedding: list[float]) -> StreamEvent:
        return cls(
            message_id=message.id,
            content=message.content,
            user_id=message.author.id,
            username=message.author.username,
            is_host=message.author.is_host,
            is_bot=message.author.is_bot,
            is_mod=message.author.is_mod,
            is_verified=message.author.is_verified,
            is_shared="source_broadcaster_id" in message.extra_metadata,
            created_at=message.created_at,
            channel_id=message.channel_id,
            source=EventSource.TWITCH,
            is_subscribed=message.author.is_subscriber,
            subscriber_tier=message.author.subscriber_tier,
            embedding=embedding,
        )
