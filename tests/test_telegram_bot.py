from __future__ import annotations

import unittest
from unittest import mock

from tetherly.telegram_bot import (
    _ARG_PROMPTS,
    _PROMPT_TEXT_TO_COMMAND,
    KEY_ALIAS_COMMANDS,
    KNOWN_COMMANDS,
    MessageIntent,
    TelegramAccessController,
    TelegramBot,
    _match_arg_prompt_reply,
    _parse_command,
    keyboard_for_intent,
    keyboard_for_status,
    keyboard_for_tail,
)


class ParseCommandTest(unittest.TestCase):
    def test_simple_command(self) -> None:
        self.assertEqual(_parse_command("/bind"), ("bind", ""))

    def test_command_with_args(self) -> None:
        self.assertEqual(
            _parse_command("/send hello world"),
            ("send", "hello world"),
        )

    def test_command_with_bot_mention_is_stripped(self) -> None:
        self.assertEqual(
            _parse_command("/bind@my_bot t1"),
            ("bind", "t1"),
        )

    def test_non_command_returns_none(self) -> None:
        self.assertIsNone(_parse_command("hello"))

    def test_lone_slash_returns_none(self) -> None:
        self.assertIsNone(_parse_command("/"))


class TelegramAccessControllerTest(unittest.TestCase):
    def test_user_id_must_be_in_allowlist(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids={111}, allowed_chat_ids=set()
        )
        self.assertTrue(ac.is_allowed(chat_id=42, user_id=111))
        self.assertFalse(ac.is_allowed(chat_id=42, user_id=222))

    def test_empty_user_allowlist_blocks_everyone(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids=set(), allowed_chat_ids=set()
        )
        self.assertFalse(ac.is_allowed(chat_id=1, user_id=1))

    def test_chat_allowlist_filters_by_chat(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids={111}, allowed_chat_ids={42}
        )
        self.assertTrue(ac.is_allowed(chat_id=42, user_id=111))
        self.assertFalse(ac.is_allowed(chat_id=99, user_id=111))

    def test_chat_trusted_admits_unlisted_user_when_chat_allowlist_set(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids={111}, allowed_chat_ids={42}
        )
        # An unlisted user passes when the chat is trusted AND the chat is on
        # the env-level chat allowlist.
        self.assertTrue(ac.is_allowed(chat_id=42, user_id=222, chat_trusted=True))
        # The privileged user is still privileged.
        self.assertTrue(ac.is_allowed(chat_id=42, user_id=111, chat_trusted=True))

    def test_chat_trusted_ignored_without_chat_allowlist(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids={111}, allowed_chat_ids=set()
        )
        # trust_chat alone does not bypass the user allowlist; the operator must
        # also pin the chat via TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS so chat
        # membership is not unbounded.
        self.assertFalse(ac.is_allowed(chat_id=42, user_id=222, chat_trusted=True))
        # The env-allowlisted user still passes through the user check.
        self.assertTrue(ac.is_allowed(chat_id=42, user_id=111, chat_trusted=True))

    def test_chat_trusted_still_honors_chat_allowlist(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids={111}, allowed_chat_ids={42}
        )
        # Even with chat_trusted, a chat outside the env chat allowlist is blocked.
        self.assertFalse(ac.is_allowed(chat_id=99, user_id=222, chat_trusted=True))

    def test_is_privileged_only_env_allowlist(self) -> None:
        ac = TelegramAccessController(
            allowed_user_ids={111}, allowed_chat_ids=set()
        )
        self.assertTrue(ac.is_privileged(111))
        self.assertFalse(ac.is_privileged(222))


def _all_callback_data(keyboard: dict) -> list[str]:
    return [
        button["callback_data"]
        for row in keyboard["inline_keyboard"]
        for button in row
    ]


class KeyboardForIntentTest(unittest.TestCase):
    def test_plain_intent_has_no_keyboard(self) -> None:
        self.assertIsNone(keyboard_for_intent(MessageIntent.PLAIN))

    def test_stop_intent_offers_enter_tail_ctrlc(self) -> None:
        kb = keyboard_for_intent(MessageIntent.STOP)
        self.assertIsNotNone(kb)
        data = _all_callback_data(kb)
        self.assertIn("key:enter", data)
        self.assertIn("tail", data)
        self.assertIn("key:ctrl-c", data)

    def test_permission_intent_offers_yes_no_tail(self) -> None:
        kb = keyboard_for_intent(MessageIntent.PERMISSION)
        self.assertIsNotNone(kb)
        data = _all_callback_data(kb)
        self.assertIn("key:enter", data)  # Yes
        self.assertIn("key:ctrl-c", data)  # No
        self.assertIn("tail", data)


class StatusTailKeyboardTest(unittest.TestCase):
    def test_status_keyboard_has_refresh_and_keys(self) -> None:
        data = _all_callback_data(keyboard_for_status())
        self.assertIn("status", data)
        self.assertIn("tail", data)
        self.assertIn("key:enter", data)
        self.assertIn("key:ctrl-c", data)

    def test_tail_keyboard_offers_refresh_and_keys(self) -> None:
        data = _all_callback_data(keyboard_for_tail())
        self.assertIn("tail", data)
        self.assertIn("key:enter", data)
        self.assertIn("key:ctrl-c", data)


class CallbackDataLengthTest(unittest.TestCase):
    """Telegram caps callback_data at 64 bytes — make sure all our data values fit."""

    def test_all_keyboard_callbacks_under_64_bytes(self) -> None:
        keyboards = [
            keyboard_for_intent(MessageIntent.STOP),
            keyboard_for_intent(MessageIntent.PERMISSION),
            keyboard_for_status(),
            keyboard_for_tail(),
        ]
        for kb in keyboards:
            if kb is None:
                continue
            for data in _all_callback_data(kb):
                self.assertLessEqual(len(data.encode("utf-8")), 64, data)


class KeyAliasCommandsTest(unittest.TestCase):
    def test_aliases_map_to_normalized_keys(self) -> None:
        self.assertEqual(KEY_ALIAS_COMMANDS["enter"], "enter")
        self.assertEqual(KEY_ALIAS_COMMANDS["esc"], "esc")
        self.assertEqual(KEY_ALIAS_COMMANDS["ctrlc"], "ctrl-c")
        self.assertEqual(KEY_ALIAS_COMMANDS["ctrld"], "ctrl-d")
        self.assertEqual(KEY_ALIAS_COMMANDS["tab"], "tab")


class ArgPromptTest(unittest.TestCase):
    def test_prompts_round_trip_to_command_names(self) -> None:
        for cmd, text in _ARG_PROMPTS.items():
            self.assertEqual(_PROMPT_TEXT_TO_COMMAND[text], cmd)

    def test_match_arg_prompt_reply_detects_bot_prompt(self) -> None:
        msg = {
            "reply_to_message": {
                "from": {"is_bot": True},
                "text": _ARG_PROMPTS["send"],
            }
        }
        self.assertEqual(_match_arg_prompt_reply(msg), "send")

    def test_match_arg_prompt_reply_ignores_non_bot_replies(self) -> None:
        msg = {
            "reply_to_message": {
                "from": {"is_bot": False},
                "text": _ARG_PROMPTS["send"],
            }
        }
        self.assertIsNone(_match_arg_prompt_reply(msg))

    def test_match_arg_prompt_reply_ignores_unrelated_messages(self) -> None:
        msg = {"reply_to_message": {"from": {"is_bot": True}, "text": "hi"}}
        self.assertIsNone(_match_arg_prompt_reply(msg))

    def test_match_arg_prompt_reply_handles_no_reply(self) -> None:
        self.assertIsNone(_match_arg_prompt_reply({}))


class KnownCommandsTest(unittest.TestCase):
    def test_includes_every_dispatch_branch(self) -> None:
        # Every name dispatched in TelegramBot._dispatch must be in
        # KNOWN_COMMANDS, otherwise the new passthrough fallthrough would
        # forward a real bot command to tmux instead of running it.
        expected = {
            "bind", "unbind", "config", "send", "key",
            "tail", "status", "help", "start",
        } | set(KEY_ALIAS_COMMANDS.keys())
        self.assertTrue(expected.issubset(KNOWN_COMMANDS))


class HandleUpdatePassthroughTest(unittest.IsolatedAsyncioTestCase):
    def _bot(self, *, binding, allow=True):
        cfg = mock.Mock(
            telegram_bot_token="t", default_tail_lines=10, max_tail_lines=100
        )
        registry = mock.Mock()
        registry.get.return_value = binding
        tmux = mock.Mock()
        ac = mock.Mock()
        ac.is_allowed.return_value = allow
        ac.is_privileged.return_value = True
        bot = TelegramBot(
            config=cfg, registry=registry, tmux_service=tmux, access_controller=ac
        )
        return bot, tmux

    def _update(self, text: str) -> dict:
        return {
            "message": {
                "chat": {"id": 100},
                "from": {"id": 200},
                "text": text,
                "message_id": 7,
            }
        }

    async def test_unknown_slash_command_forwarded_when_auto_send_on(self) -> None:
        binding = mock.Mock(session_name="s1", auto_send=True, trust_chat=False)
        bot, tmux = self._bot(binding=binding)

        await bot._handle_update(session=None, update=self._update("/clear"))

        tmux.send_text.assert_called_once_with("s1", "/clear", press_enter=True)

    async def test_unknown_slash_command_dropped_when_auto_send_off(self) -> None:
        binding = mock.Mock(session_name="s1", auto_send=False, trust_chat=False)
        bot, tmux = self._bot(binding=binding)

        await bot._handle_update(session=None, update=self._update("/clear"))

        tmux.send_text.assert_not_called()

    async def test_known_slash_command_does_not_passthrough(self) -> None:
        # `/status` is a real bot command — it must not be forwarded to tmux.
        binding = mock.Mock(session_name="s1", auto_send=True, trust_chat=False)
        bot, tmux = self._bot(binding=binding)

        with mock.patch.object(bot, "_dispatch", new=mock.AsyncMock()) as dispatch:
            await bot._handle_update(session=None, update=self._update("/status"))

        tmux.send_text.assert_not_called()
        dispatch.assert_awaited_once()
        self.assertEqual(dispatch.await_args.args[3], "status")


if __name__ == "__main__":
    unittest.main()
