import logging

from twitchio.ext import commands
from core.config import settings
from ingestion.message_buffer import MessageBuffer

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


COMMAND_PREFIX = "!"


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
            prefix="!",
        )
        self._message_buffer = message_buffer
        # TODO: create validator checking if channel is live
        self._can_listen = True

    async def event_ready(self) -> None:
        """
        Handle the bot-ready event fired by TwitchIO once the connection is established.

        Prints a startup banner with operator and channel info when the bot is
        permitted to listen (``_can_listen`` is ``True``), otherwise logs that
        the stream is unavailable.
        """
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

    def _is_command(self, text: str) -> bool:
        """
        Check whether a chat message is a bot command.

        Args:
            text: Raw message text from Twitch chat.

        Returns:
            ``True`` if the message starts with ``COMMAND_PREFIX`` (``!``),
            ``False`` otherwise.
        """
        return text.startswith(COMMAND_PREFIX)
