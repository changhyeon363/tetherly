from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from co_agent.session_registry import SessionRegistry


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
            payload = json.loads(state_path.read_text())
            self.assertEqual(payload["bindings"][0]["channel_id"], 2)

            reloaded = SessionRegistry(state_path)
            self.assertIsNotNone(reloaded.get(2))
            self.assertEqual(reloaded.get(2).session_name, "main")


if __name__ == "__main__":
    unittest.main()
