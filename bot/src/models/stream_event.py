from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SubscriberTier(Enum):
    """Twitch subscription tier of the chatter at the time the message was sent."""

    TIER_1 = "1000"
    TIER_2 = "2000"
    TIER_3 = "3000"


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
    is_moderator: bool
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
