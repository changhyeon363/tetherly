from __future__ import annotations

import unittest

from tetherly.telegram_bot import TelegramAccessController, _parse_command


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


if __name__ == "__main__":
    unittest.main()
