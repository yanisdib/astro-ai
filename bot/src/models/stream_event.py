from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from models.twitch_user import TwitchUser

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
class EventSemantics:
    """AI-enriched analysis computed during ingestion."""

    embedding: list[float] = field(default_factory=list)
    intent_category: Optional[IntentCategory] = IntentCategory.CHATTING
    topics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StreamEvent:
    """
    Platform-agnostic Data Transfer Object representing a single immutable chat event.
    """

    # Message data
    message_id: str
    content: str
    is_shared: bool
    created_at: int

    # Channel / platform metadata
    channel_id: str
    source: EventSource

    # Author snapshot at message time
    author: TwitchUser

    # Semantic intelligence (populated during ingestion)
    semantics: EventSemantics = field(default_factory=EventSemantics)

    @classmethod
    def from_twitch_message(
        cls, message: TwitchMessage, embedding: list[float]
    ) -> StreamEvent:
        return cls(
            message_id=message.id,
            content=message.content,
            is_shared="source_broadcaster_id" in message.extra_metadata,
            created_at=message.created_at,
            channel_id=message.channel_id,
            source=EventSource.TWITCH,
            author=message.author,
            semantics=EventSemantics(embedding=embedding),
        )

    def to_document_row(self) -> dict[str, Any]:
        """Map this event to flat bind parameters for the documents table INSERT."""
        return {
            "message_id": self.message_id,
            "message_content": self.content,
            "shared_stream": self.is_shared,
            "channel_id": self.channel_id,
            "source": self.source.value,
            "user_id": self.author.id,
            "username": self.author.username,
            "is_astro": self.author.is_astro,
            "is_bot": self.author.is_bot,
            "is_mod": self.author.is_mod,
            "is_broadcaster": self.author.is_broadcaster,
            "is_verified": self.author.is_verified,
            "is_partner": self.author.is_partner,
            "is_affiliate": self.author.is_affiliate,
            "is_subscriber": self.author.is_subscriber,
            "with_prime": self.author.with_prime,
            "subscriber_tier": (
                self.author.subscriber_tier.value
                if self.author.subscriber_tier
                else None
            ),
            "embedding": self.semantics.embedding,
            "intent_category": (
                self.semantics.intent_category.value
                if self.semantics.intent_category
                else None
            ),
            "topics": self.semantics.topics,
            "created_at": datetime.fromtimestamp(self.created_at, tz=UTC),
        }
