from __future__ import annotations

import unittest

from tetherly.telegram_sender import TelegramSendError, split_message


class SplitMessageTest(unittest.TestCase):
    def test_short_message_passes_through(self) -> None:
        self.assertEqual(split_message("hello"), ["hello"])

    def test_rejects_empty(self) -> None:
        with self.assertRaises(TelegramSendError):
            split_message("   ")

    def test_chunks_long_message(self) -> None:
        chunks = split_message("a" * 9000, limit=4096)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(sum(len(chunk) for chunk in chunks), 9000)

    def test_prefers_newline_split(self) -> None:
        text = "alpha\nbeta\ngamma\ndelta"
        chunks = split_message(text, limit=12)
        for chunk in chunks:
            self.assertNotIn(" ", chunk)
            self.assertLessEqual(len(chunk), 12)
        for chunk in chunks[:-1]:
            self.assertFalse(chunk.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
