import logging

from twitchio.ext import commands
from core.config import config
from ingestion.message_buffer import MessageBuffer

logging.basicConfig(level=config.LOG_LEVEL)
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
            client_id=config.TWITCH_CLIENT_ID,
            client_secret=config.TWITCH_CLIENT_SECRET,
            bot_id=config.TWITCH_BOT_ID,
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
            print("\n" + "=" * 40)
            print("⚡ ASTRO ENGINE ACTIVATED")
            print(f"OPERATOR: {self.user.display_name}")
            print(f"SOURCE:   {config.TWITCH_CHANNEL}")
            print("-" * 40)
            print("CORE SYSTEMS STATUS:")
            print("  > Memory Core:     INITIALIZED")
            print("  > Safety Shield:   ARMED")
            print("  > Skill Engine:    STANDBY")
            print("=" * 40 + "\n")

            logger.info(
                "Synchronization complete. Processing Data into Collective Memory."
            )
        else:
            logger.info("Energy Stream is currently not accessible.")

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
