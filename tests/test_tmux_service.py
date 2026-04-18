from __future__ import annotations

from unittest import mock
import unittest

from co_agent.tmux_service import TmuxService, normalize_session_name


class TmuxServiceTest(unittest.TestCase):
    def test_normalize_session_name(self) -> None:
        self.assertEqual(normalize_session_name(" main room "), "main-room")

    @mock.patch("co_agent.tmux_service.subprocess.run")
    @mock.patch.dict("co_agent.tmux_service.os.environ", {"TMUX_PANE": "%1"}, clear=False)
    def test_get_current_session_name(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = mock.Mock(returncode=0, stdout="t1\n", stderr="")
        service = TmuxService()
        self.assertEqual(service.get_current_session_name(), "t1")


if __name__ == "__main__":
    unittest.main()
