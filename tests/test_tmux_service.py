from __future__ import annotations

import unittest

from co_agent.tmux_service import normalize_session_name


class TmuxServiceTest(unittest.TestCase):
    def test_normalize_session_name(self) -> None:
        self.assertEqual(normalize_session_name(" main room "), "main-room")


if __name__ == "__main__":
    unittest.main()
