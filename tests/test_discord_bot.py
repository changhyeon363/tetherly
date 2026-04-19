from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest import mock

import discord

from co_agent.discord_bot import _extract_auto_send_text
from co_agent.discord_bot import CoAgentBot


class ExtractAutoSendTextTest(unittest.TestCase):
    def _message(self, **overrides: object) -> SimpleNamespace:
        payload = {
            "author": SimpleNamespace(bot=False),
            "webhook_id": None,
            "guild": SimpleNamespace(id=1),
            "channel": SimpleNamespace(id=10),
            "type": discord.MessageType.default,
            "reference": None,
            "attachments": [],
            "content": "hello",
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    def test_accepts_plain_text_message(self) -> None:
        message = self._message(content="  hello codex  ")

        self.assertEqual(_extract_auto_send_text(message), "hello codex")

    def test_rejects_slash_like_message(self) -> None:
        message = self._message(content="/send hi")

        self.assertIsNone(_extract_auto_send_text(message))

    def test_rejects_reply_message(self) -> None:
        message = self._message(reference=object())

        self.assertIsNone(_extract_auto_send_text(message))

    def test_rejects_message_with_attachments(self) -> None:
        message = self._message(attachments=[object()])

        self.assertIsNone(_extract_auto_send_text(message))

    def test_rejects_thread_message(self) -> None:
        class FakeThread:
            id = 10

        message = self._message(channel=FakeThread())

        with mock.patch("co_agent.discord_bot.discord.Thread", FakeThread):
            self.assertIsNone(_extract_auto_send_text(message))


class OnMessageTest(unittest.IsolatedAsyncioTestCase):
    async def test_ignores_dm_message_without_guild(self) -> None:
        bot = CoAgentBot(
            config=mock.Mock(test_guild_id=None),
            registry=mock.Mock(),
            tmux_service=mock.Mock(),
            access_controller=mock.Mock(),
        )
        message = SimpleNamespace(
            guild=None,
            channel=SimpleNamespace(id=10),
        )

        await bot.on_message(message)

        bot.registry.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
