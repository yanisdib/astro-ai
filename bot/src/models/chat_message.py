from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class ChatMessage:
    """
    Core Data Transfer Object representing a single immutable Twitch chat message.
    Encapsulates Twitch message data for system-wide processing.
    """

    id: str
    content: str
    user_id: str
    username: str
    is_bot: bool
    is_mod: bool
    is_command: bool
    created_at: int
    extra_metadata: Dict[str, Any] = field(default_factory=dict)
