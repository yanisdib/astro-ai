from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

from models.twitch_badge import TwitchBadge

if TYPE_CHECKING:
    from twitchio import Chatter


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
    is_astro: bool
    is_bot: bool
    is_mod: bool
    is_broadcaster: bool
    is_verified: bool
    is_partner: bool
    is_affiliate: bool
    is_subscriber: bool
    with_prime: bool
    subscriber_tier: Optional[SubscriberTier] = None

    @classmethod
    def from_chatter(cls, chatter: Chatter, bot_id: str) -> TwitchUser:
        """
        Build a ``TwitchUser`` snapshot from a TwitchIO ``Chatter`` object.

        Parses the full badge list in a single pass via ``TwitchBadge.parse_all``,
        then derives every boolean flag from the resulting mapping. Prefer this
        over constructing ``TwitchUser`` directly whenever a raw ``Chatter`` is
        available — badge derivation logic lives here, not in the caller.

        Args:
            chatter: The ``Chatter`` attached to an incoming ``ChatMessage``.
            bot_id:  The Twitch user ID of the bot account, used to set ``is_astro``.

        Returns:
            An immutable ``TwitchUser`` snapshot reflecting the chatter's identity
            and status at the moment the message was sent.

        Note:
            ``is_verified`` and ``is_partner`` are both derived from the ``partner``
            badge — they are equivalent from chat-badge data alone.
            ``subscriber_tier`` is derived from the subscriber badge's ``id`` range;
            see ``_subscriber_tier`` for the encoding details.
        """
        badges = TwitchBadge.parse_all(chatter.badges)

        return cls(
            id=chatter.id,
            username=chatter.name or chatter.id,
            is_astro=chatter.id == bot_id,
            is_bot=TwitchBadge.BOT in badges,
            is_mod=chatter.moderator,
            is_broadcaster=chatter.broadcaster,
            is_verified=TwitchBadge.VERIFIED in badges,
            is_partner=TwitchBadge.PARTNER in badges,
            is_affiliate=TwitchBadge.AFFILIATE in badges,
            is_subscriber=TwitchBadge.SUBSCRIBER in badges,
            with_prime=TwitchBadge.PRIME in badges,
            subscriber_tier=None,  # TODO: use chatter info to determine
        )
