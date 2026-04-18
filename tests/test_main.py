from __future__ import annotations

import os
import unittest
from unittest import mock

from co_agent.main import resolve_session_name


class ResolveSessionNameTest(unittest.TestCase):
    def test_prefers_explicit_session(self) -> None:
        tmux_service = mock.Mock()
        self.assertEqual(
            resolve_session_name("t1", tmux_service=tmux_service),
            "t1",
        )

    @mock.patch.dict(os.environ, {"CO_AGENT_SESSION": "from-env"}, clear=False)
    def test_uses_environment_session(self) -> None:
        tmux_service = mock.Mock()
        self.assertEqual(
            resolve_session_name(None, tmux_service=tmux_service),
            "from-env",
        )

    def test_uses_tmux_environment_session(self) -> None:
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "pane-session"
        tmux_service.get_session_environment.return_value = "bound-session"
        self.assertEqual(
            resolve_session_name(None, tmux_service=tmux_service),
            "bound-session",
        )

    def test_falls_back_to_current_tmux_session(self) -> None:
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "pane-session"
        tmux_service.get_session_environment.return_value = None
        self.assertEqual(
            resolve_session_name(None, tmux_service=tmux_service),
            "pane-session",
        )


if __name__ == "__main__":
    unittest.main()
