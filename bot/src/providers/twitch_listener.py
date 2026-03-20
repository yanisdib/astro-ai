import logging

from typing import Any
from twitchio.ext import commands
from twitchio import HTTPException, ChatMessage
from aiohttp import ClientConnectionError

from core.config import settings
from ingestion.message_buffer import MessageBuffer

from models.twitch_message import TwitchMessage
from models.twitch_user import TwitchUser
from models.twitch_badge import TwitchBadge

from utils.decorators import retry

logger = logging.getLogger("TwitchChatListener")


class TwitchChatListener(commands.Bot):
    def __init__(self, message_buffer: MessageBuffer) -> None:
        """
        Initialize the Twitch chat listener bot.

        Args:
            message_buffer: Buffer used to accumulate incoming chat messages
                before flushing them to the ingestion pipeline.
        """
        # TODO: Current account is Mako AI. It should be a new account for the Bot.
        super().__init__(
            client_id=settings.TWITCH_CLIENT_ID,
            client_secret=settings.TWITCH_CLIENT_SECRET,
            bot_id=settings.TWITCH_BOT_ID,
            prefix=settings.TWITCH_COMMAND_PREFIX,
        )
        self._message_buffer = message_buffer
        self._can_listen = False

    async def event_ready(self) -> None:
        """
        Handle the bot-ready event fired by TwitchIO once the connection is established.

        Checks whether the configured channel is currently live, then prints a startup
        banner if listening is permitted, otherwise logs that the stream is unavailable.
        """
        try:
            self._can_listen = await self._is_live()
        except Exception as e:
            logger.error("Failed to check stream status: %s. Bot will not listen.", e)

        if self._can_listen:
            print("\n" + "─" * 44)
            print("  A S T R O  ·  GHOST SIGNAL ACQUIRED")
            print("─" * 44)
            print(f"  SHELL      {self.user.display_name}")
            print(f"  NET NODE   {settings.TWITCH_CHANNEL}")
            print("─" * 44)
            print("  ENGINE              STATE")
            print("  · · · · · · · · · · · · · · · · · · · ")
            print("  Memory Core       ■ SYNCHRONIZED")
            print("  Filter Drive      ■ THROTTLED")
            print("  Ghost Engine      ○ DORMANT")
            print("─" * 44)
            print("  scanning the net.\n")

            logger.info("Ghost is live. Ingestion engines running.")
        else:
            logger.info("Net feed unavailable. Standing by.")

    async def event_message(self, message: ChatMessage) -> None:
        if not message.metadata:
            return

        badges = message.chatter.badges
        author = TwitchUser(
            id=message.chatter.id,
            username=message.chatter.name or message.chatter.id,
            is_astro=message.chatter.id == settings.TWITCH_BOT_ID,
            is_bot=TwitchBadge.BOT in badges,
            is_mod=message.chatter.moderator,
            is_broadcaster=message.chatter.broadcaster,
            is_verified=TwitchBadge.VERIFIED in badges,
            is_partner=TwitchBadge.PARTNER in badges,
            is_affiliate=TwitchBadge.AFFILIATE in badges,
            is_subscriber=TwitchBadge.SUBSCRIBER in badges,
            with_prime=TwitchBadge.PRIME in badges,
        )

        new_message = TwitchMessage(
            id=message.metadata.message_id,
            content=message.text,
            author=author,
            channel_id=str(message.broadcaster.id),
            is_command=self._is_bot_command(message.text),
            created_at=int(message.metadata.message_timestamp.timestamp()),
            extra_metadata=self._get_shared_chat_details(message) or {},
        )

        await self._message_buffer.queue_message(message=new_message)

    def _get_shared_chat_details(self, message: ChatMessage) -> dict[str, Any] | None:
        broadcaster_id = getattr(message.metadata, "source_broadcaster_user_id", None)
        if broadcaster_id is None:
            return None

        return {
            "source_broadcaster_id": broadcaster_id,
            "source_broadcaster_login": getattr(
                message.metadata, "source_broadcaster_user_login", None
            ),
        }

    def _is_bot_command(self, text: str) -> bool:
        """
        Check whether a chat message is a bot command.

        Args:
            text: Raw message text from Twitch chat.

        Returns:
            ``True`` if the message starts with ``COMMAND_PREFIX`` (``!``) and the term `astro`,
            ``False`` otherwise.
        """
        return text.startswith(settings.TWITCH_COMMAND_PREFIX + "astro")

    @retry(retry_on=(HTTPException, ClientConnectionError))
    async def _is_live(self) -> bool:
        """
        Check whether the configured Twitch channel is currently live.

        Uses the bot's app token to query the Helix streams endpoint — no
        channel user credentials required. Retries on transient HTTP and
        network errors with exponential backoff.

        Returns:
            bool: True if the channel has an active stream, False otherwise.

        Raises:
            HTTPException | ClientConnectionError: Propagated after all retries
                are exhausted.
        """
        streams = await self.fetch_streams(user_logins=[settings.TWITCH_CHANNEL])
        return len(streams) > 0
