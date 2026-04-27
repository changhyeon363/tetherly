from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tetherly.discord_sender import DiscordSendError, split_message
from tetherly.session_registry import SessionRegistry, SessionRegistryError


class DiscordSenderTest(unittest.TestCase):
    def test_split_message_preserves_short_message(self) -> None:
        self.assertEqual(split_message("hello"), ["hello"])

    def test_split_message_rejects_empty(self) -> None:
        with self.assertRaises(DiscordSendError):
            split_message("   ")

    def test_split_message_chunks_long_message(self) -> None:
        chunks = split_message("a" * 4100, limit=2000)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(sum(len(chunk) for chunk in chunks), 4100)

    def test_registry_blocks_duplicate_session_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = SessionRegistry(Path(tmpdir) / "state.json")
            registry.bind(guild_id=1, channel_id=10, session_name="t1", bound_by=5)
            with self.assertRaises(SessionRegistryError):
                registry.bind(guild_id=1, channel_id=11, session_name="t1", bound_by=5)


if __name__ == "__main__":
    unittest.main()
