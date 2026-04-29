from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tetherly.models import PLATFORM_DISCORD, PLATFORM_TELEGRAM
from tetherly.session_registry import SessionRegistry, SessionRegistryError


class SessionRegistryTest(unittest.TestCase):
    def test_registry_persists_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            registry = SessionRegistry(state_path)

            binding = registry.bind(
                guild_id=1,
                channel_id=2,
                session_name="main",
                bound_by=3,
            )

            self.assertEqual(binding.session_name, "main")
            self.assertFalse(binding.auto_send)
            payload = json.loads(state_path.read_text())
            self.assertEqual(payload["bindings"][0]["channel_id"], 2)

            reloaded = SessionRegistry(state_path)
            self.assertIsNotNone(reloaded.get(2))
            self.assertEqual(reloaded.get(2).session_name, "main")
            self.assertFalse(reloaded.get(2).auto_send)

    def test_set_auto_send_persists_setting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            registry = SessionRegistry(state_path)
            registry.bind(
                guild_id=1,
                channel_id=2,
                session_name="main",
                bound_by=3,
            )

            updated = registry.set_auto_send(2, True)

            self.assertIsNotNone(updated)
            self.assertTrue(updated.auto_send)
            reloaded = SessionRegistry(state_path)
            self.assertTrue(reloaded.get(2).auto_send)


    def test_rejects_session_already_bound_to_other_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            registry = SessionRegistry(state_path)
            registry.bind(
                guild_id=1,
                channel_id=10,
                session_name="t1",
                bound_by=5,
                platform=PLATFORM_DISCORD,
            )
            with self.assertRaises(SessionRegistryError):
                registry.bind(
                    guild_id=99,
                    channel_id=200,
                    session_name="t1",
                    bound_by=5,
                    platform=PLATFORM_TELEGRAM,
                )

    def test_unbind_removes_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            registry = SessionRegistry(state_path)
            registry.bind(
                guild_id=1,
                channel_id=2,
                session_name="main",
                bound_by=3,
            )
            removed = registry.unbind(2)
            self.assertIsNotNone(removed)
            self.assertIsNone(registry.get(2))
            reloaded = SessionRegistry(state_path)
            self.assertIsNone(reloaded.get(2))

    def test_loads_old_state_without_platform_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "bindings": [
                            {
                                "guild_id": 1,
                                "channel_id": 2,
                                "session_name": "legacy",
                                "auto_send": False,
                                "bound_by": 3,
                                "bound_at": "2026-01-01T00:00:00+00:00",
                                "last_used_at": "2026-01-01T00:00:00+00:00",
                            }
                        ]
                    }
                )
            )
            registry = SessionRegistry(state_path)
            binding = registry.get(2)
            self.assertIsNotNone(binding)
            self.assertEqual(binding.platform, PLATFORM_DISCORD)


if __name__ == "__main__":
    unittest.main()
