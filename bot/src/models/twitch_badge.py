from enum import Enum


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
