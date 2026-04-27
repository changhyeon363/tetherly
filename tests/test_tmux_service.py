from __future__ import annotations

from unittest import mock
import unittest

from co_agent.tmux_service import TmuxError, TmuxService, normalize_session_name


class TmuxServiceTest(unittest.TestCase):
    def test_normalize_session_name(self) -> None:
        self.assertEqual(normalize_session_name(" main room "), "main-room")

    @mock.patch("co_agent.tmux_service.subprocess.run")
    @mock.patch.dict("co_agent.tmux_service.os.environ", {"TMUX_PANE": "%1"}, clear=False)
    def test_get_current_session_name(self, run_mock: mock.Mock) -> None:
        run_mock.return_value = mock.Mock(returncode=0, stdout="t1\n", stderr="")
        service = TmuxService()
        self.assertEqual(service.get_current_session_name(), "t1")

    @mock.patch.object(TmuxService, "session_exists", return_value=True)
    @mock.patch.object(TmuxService, "_run")
    def test_send_key_normalizes_alias(self, run_mock: mock.Mock, _: mock.Mock) -> None:
        service = TmuxService()

        service.send_key("t1", "esc")

        run_mock.assert_called_once_with("send-keys", "-t", "t1", "Escape")

    @mock.patch.object(TmuxService, "session_exists", return_value=True)
    def test_send_key_rejects_unsupported_key(self, _: mock.Mock) -> None:
        service = TmuxService()

        with self.assertRaises(TmuxError):
            service.send_key("t1", "space")


if __name__ == "__main__":
    unittest.main()
