import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from twitchio.ext import commands

from providers.twitch_listener import TwitchChatListener
from models.twitch_message import TwitchMessage
from models.twitch_user import TwitchUser


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_buffer():
    buf = MagicMock()
    buf.queue_message = AsyncMock()
    return buf


@pytest.fixture
def listener(mock_buffer):
    """Create a TwitchChatListener with the TwitchIO bot initialisation bypassed."""
    with patch.object(commands.Bot, "__init__", return_value=None):
        bot = TwitchChatListener(message_buffer=mock_buffer)
    return bot


def _make_author() -> TwitchUser:
    return TwitchUser(
        id="user-42",
        username="streamer_fan",
        is_astro=False,
        is_bot=False,
        is_mod=False,
        is_broadcaster=False,
        is_verified=False,
        is_partner=False,
        is_affiliate=False,
        is_subscriber=False,
        with_prime=False,
    )


def _make_chat_message(
    text: str = "hello world",
    message_id: str = "msg-1",
    broadcaster_id: str = "channel-99",
    source_broadcaster_id: str | None = None,
) -> MagicMock:
    """Build a minimal ChatMessage mock mirroring TwitchIO's structure."""
    ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    metadata = SimpleNamespace(
        message_id=message_id,
        message_timestamp=ts,
    )
    if source_broadcaster_id is not None:
        metadata.source_broadcaster_user_id = source_broadcaster_id
        metadata.source_broadcaster_user_login = "shared_login"

    msg = MagicMock()
    msg.metadata = metadata
    msg.text = text
    msg.chatter = MagicMock()
    msg.broadcaster = MagicMock()
    msg.broadcaster.id = broadcaster_id
    return msg


# ---------------------------------------------------------------------------
# _is_bot_command
# ---------------------------------------------------------------------------

class TestIsBotCommand:
    def test_exact_command(self, listener):
        assert listener._is_bot_command("!astro") is True

    def test_command_with_args(self, listener):
        assert listener._is_bot_command("!astro who is winning?") is True

    def test_command_prefix_only_no_astro(self, listener):
        assert listener._is_bot_command("!hello") is False

    def test_regular_chat_message(self, listener):
        assert listener._is_bot_command("hello world") is False

    def test_case_sensitive_prefix(self, listener):
        # Commands are case-sensitive — uppercase should NOT match
        assert listener._is_bot_command("!ASTRO") is False

    def test_empty_string(self, listener):
        assert listener._is_bot_command("") is False


# ---------------------------------------------------------------------------
# _get_shared_chat_details
# ---------------------------------------------------------------------------

class TestGetSharedChatDetails:
    def test_returns_none_when_no_source_broadcaster(self, listener):
        msg = _make_chat_message()
        result = listener._get_shared_chat_details(msg)
        assert result is None

    def test_returns_dict_with_source_broadcaster(self, listener):
        msg = _make_chat_message(source_broadcaster_id="broadcaster-7")
        result = listener._get_shared_chat_details(msg)
        assert result == {
            "source_broadcaster_id": "broadcaster-7",
            "source_broadcaster_login": "shared_login",
        }

    def test_login_can_be_none(self, listener):
        msg = _make_chat_message(source_broadcaster_id="broadcaster-7")
        del msg.metadata.source_broadcaster_user_login  # remove the attribute entirely
        result = listener._get_shared_chat_details(msg)
        assert result["source_broadcaster_login"] is None


# ---------------------------------------------------------------------------
# event_message
# ---------------------------------------------------------------------------

class TestEventMessage:
    async def test_skips_message_without_metadata(self, listener, mock_buffer):
        msg = MagicMock()
        msg.metadata = None

        await listener.event_message(payload=msg)

        mock_buffer.queue_message.assert_not_called()

    async def test_queues_regular_message(self, listener, mock_buffer):
        msg = _make_chat_message(text="great stream!", message_id="msg-99")
        author = _make_author()

        with (
            patch("providers.twitch_listener.TwitchUser.from_chatter", return_value=author),
            patch("providers.twitch_listener.settings") as mock_settings,
        ):
            mock_settings.TWITCH_BOT_ID = "bot-1"
            mock_settings.TWITCH_COMMAND_PREFIX = "!"

            await listener.event_message(msg)

        mock_buffer.queue_message.assert_awaited_once()
        queued: TwitchMessage = mock_buffer.queue_message.call_args.kwargs["message"]
        assert queued.id == "msg-99"
        assert queued.content == "great stream!"
        assert queued.author is author
        assert queued.channel_id == "channel-99"
        assert queued.is_command is False

    async def test_marks_bot_command(self, listener, mock_buffer):
        msg = _make_chat_message(text="!astro who are you?")
        author = _make_author()

        with (
            patch("providers.twitch_listener.TwitchUser.from_chatter", return_value=author),
            patch("providers.twitch_listener.settings") as mock_settings,
        ):
            mock_settings.TWITCH_BOT_ID = "bot-1"
            mock_settings.TWITCH_COMMAND_PREFIX = "!"

            await listener.event_message(msg)

        queued: TwitchMessage = mock_buffer.queue_message.call_args.kwargs["message"]
        assert queued.is_command is True

    async def test_includes_shared_chat_metadata(self, listener, mock_buffer):
        msg = _make_chat_message(text="hi", source_broadcaster_id="ext-99")
        author = _make_author()

        with (
            patch("providers.twitch_listener.TwitchUser.from_chatter", return_value=author),
            patch("providers.twitch_listener.settings") as mock_settings,
        ):
            mock_settings.TWITCH_BOT_ID = "bot-1"
            mock_settings.TWITCH_COMMAND_PREFIX = "!"

            await listener.event_message(msg)

        queued: TwitchMessage = mock_buffer.queue_message.call_args.kwargs["message"]
        assert queued.extra_metadata["source_broadcaster_id"] == "ext-99"

    async def test_extra_metadata_defaults_to_empty_dict(self, listener, mock_buffer):
        msg = _make_chat_message(text="hi")  # no shared chat
        author = _make_author()

        with (
            patch("providers.twitch_listener.TwitchUser.from_chatter", return_value=author),
            patch("providers.twitch_listener.settings") as mock_settings,
        ):
            mock_settings.TWITCH_BOT_ID = "bot-1"
            mock_settings.TWITCH_COMMAND_PREFIX = "!"

            await listener.event_message(msg)

        queued: TwitchMessage = mock_buffer.queue_message.call_args.kwargs["message"]
        assert queued.extra_metadata == {}


# ---------------------------------------------------------------------------
# event_ready
# ---------------------------------------------------------------------------

class TestEventReady:
    async def test_can_listen_true_when_live(self, listener):
        mock_user = MagicMock(display_name="AstroBot")

        with (
            patch.object(type(listener), "user", new_callable=PropertyMock, return_value=mock_user),
            patch.object(listener, "_is_live", AsyncMock(return_value=True)),
            patch("providers.twitch_listener.settings") as mock_settings,
        ):
            mock_settings.TWITCH_CHANNEL = "some_channel"
            await listener.event_ready()

        assert listener._can_listen is True

    async def test_can_listen_false_when_offline(self, listener):
        with (
            patch.object(type(listener), "user", new_callable=PropertyMock, return_value=MagicMock()),
            patch.object(listener, "_is_live", AsyncMock(return_value=False)),
        ):
            await listener.event_ready()

        assert listener._can_listen is False

    async def test_can_listen_false_on_exception(self, listener, caplog):
        with (
            patch.object(listener, "_is_live", AsyncMock(side_effect=RuntimeError("network down"))),
        ):
            await listener.event_ready()

        assert listener._can_listen is False
        assert "Failed to check stream status" in caplog.text


# ---------------------------------------------------------------------------
# _is_live
# ---------------------------------------------------------------------------

class TestIsLive:
    async def test_returns_true_when_streams_present(self, listener):
        with patch.object(listener, "fetch_streams", AsyncMock(return_value=["stream_obj"])):
            result = await listener._is_live()
        assert result is True

    async def test_returns_false_when_no_streams(self, listener):
        with patch.object(listener, "fetch_streams", AsyncMock(return_value=[])):
            result = await listener._is_live()
        assert result is False
