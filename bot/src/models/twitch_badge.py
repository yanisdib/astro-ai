from enum import Enum
from typing import Optional
from twitchio import ChatMessageBadge


class TwitchBadge(Enum):
    # --- Broadcaster Types (Contract Status) ---
    PARTNER = "partner"  # The "Verified" Purple Checkmark
    AFFILIATE = "affiliate"  # Monetized but no unique badge

    # --- Authority & Staff (Global) ---
    STAFF = "staff"  # Twitch Employees (wrench)
    ADMIN = "admin"  # Twitch Admins (shield)
    GLOBAL_MOD = "global_mod"  # Global Moderators (axe)

    # --- Channel Specific Roles ---
    BROADCASTER = "broadcaster"  # The streamer
    MODERATOR = "moderator"  # Channel mods (sword)
    VIP = "vip"  # Channel VIPs (diamond)
    ARTIST = "artist-badge"  # Channel artists

    # --- Support & Monetization ---
    SUBSCRIBER = "subscriber"  # Monthly subs
    FOUNDER = "founder"  # First supporters
    PRIME = "premium"  # Prime Gaming (crown)
    TURBO = "turbo"  # Twitch Turbo
    BITS = "bits"  # Bit cheerers

    # --- Specialized ---
    VERIFIED = "partner"  # Alias for Partner (the checkmark)
    BOT = "bot"  # Verified bot status

    @classmethod
    def parse(cls, badge: ChatMessageBadge) -> tuple[Optional["TwitchBadge"], str]:
        """
        Map a raw TwitchIO badge to its enum member and a context-specific detail string.

        Args:
            badge: A ``ChatMessageBadge`` as returned by ``message.chatter.badges``.
                Relevant fields:
                    - ``set_id``  — badge category (e.g. ``"subscriber"``, ``"bits"``).
                    - ``id``      — badge version or tier within the category.
                    - ``info``    — extra metadata; only populated for subscriber/founder
                                    badges, containing total months subscribed.

        Returns:
            A ``(status, details)`` tuple where:
            - ``status``  is the matching ``TwitchBadge`` member, or ``None`` if the
                        badge's ``set_id`` is not recognised.
            - ``details`` is ``badge.info`` (cumulative months) for ``SUBSCRIBER`` and
                        ``FOUNDER`` badges, or ``badge.id`` (version/tier string) for
                        all other badge types. Empty string when the field is absent.
        """
        try:
            status = cls(badge.set_id)
        except ValueError:
            status = None

        if status in (TwitchBadge.SUBSCRIBER, TwitchBadge.FOUNDER):
            details = badge.info or ""
        else:
            details = badge.id or ""

        return status, details

    @classmethod
    def parse_all(cls, badge_list: list[ChatMessageBadge]) -> dict["TwitchBadge", str]:
        """
        Parse an entire badge list into a single ``{TwitchBadge: details}`` mapping.

        Prefer this over calling ``get_badge_info`` once per flag — it walks
        ``badge_list`` only once regardless of how many flags need to be derived.
        Unrecognised badges (``set_id`` not in the enum) are silently skipped.

        Args:
            badge_list: Raw badges from ``message.chatter.badges``.

        Returns:
            A dict mapping each recognised ``TwitchBadge`` to its detail string
            (see ``parse`` for per-badge semantics).
        """
        result: dict[TwitchBadge, str] = {}
        for badge in badge_list:
            name, details = cls.parse(badge)
            if name is not None:
                result[name] = details
        return result

    @classmethod
    def get_badge_info(
        cls, badge_list: list[ChatMessageBadge], target: "TwitchBadge"
    ) -> tuple[bool, str]:
        """
        Look up a specific badge in a chatter's badge list.

        Iterates ``badge_list`` and delegates each entry to ``parse``. Stops at the
        first match and returns its associated detail string (see ``parse`` for
        semantics). Badge lists are typically short (≤ 5 entries), so linear scan
        is fine.

        Args:
            badge_list: Raw badges from ``message.chatter.badges``.
            target:     The ``TwitchBadge`` to search for.

        Returns:
            ``(True, details)`` if ``target`` is present, ``(False, "")`` otherwise.
        """
        for badge in badge_list:
            name, details = cls.parse(badge)
            if name == target:
                return True, details

        return False, ""
