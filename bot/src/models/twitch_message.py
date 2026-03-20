from dataclasses import dataclass, field
from typing import Dict, Any

from models.twitch_user import TwitchUser


@dataclass(frozen=True)
class TwitchMessage:
    """
    Core Data Transfer Object representing a single immutable Twitch chat message.
    Encapsulates raw Twitch message data for system-wide processing.
    """

    id: str
    content: str
    author: TwitchUser
    channel_id: str
    is_command: bool
    created_at: int
    extra_metadata: Dict[str, Any] = field(default_factory=dict)
