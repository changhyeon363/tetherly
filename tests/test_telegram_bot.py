from __future__ import annotations

import unittest

from tetherly.telegram_bot import (
    KEY_ALIAS_COMMANDS,
    MessageIntent,
    TelegramAccessController,
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


if __name__ == "__main__":
    unittest.main()
