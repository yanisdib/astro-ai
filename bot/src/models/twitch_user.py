from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SubscriberTier(Enum):
    """Twitch subscription tier of the chatter at the time the message was sent.

    Values match the tier identifiers returned by the Twitch API:
    https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/#channelsubscribe
    """

    TIER_1 = "1000"
    TIER_2 = "2000"
    TIER_3 = "3000"


@dataclass(frozen=True)
class TwitchUser:
    """Snapshot of a Twitch chatter's identity and status at the time a message was sent."""

    id: str
    username: str
    is_bot: bool
    is_mod: bool
    is_host: bool
    is_verified: bool
    is_subscriber: bool
    subscriber_tier: Optional[SubscriberTier] = None
