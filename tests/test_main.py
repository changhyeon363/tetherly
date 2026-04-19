from __future__ import annotations

import os
import unittest
from unittest import mock

from co_agent.main import (
    resolve_session_name,
    run_codex_notify,
    run_codex_permission_request,
)


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


class RunCodexNotifyTest(unittest.TestCase):
    def test_ignores_non_turn_complete_events(self) -> None:
        args = mock.Mock(payload='{"type":"other"}')
        with mock.patch("co_agent.main.TmuxService") as tmux_service_cls:
            self.assertEqual(
                run_codex_notify(args, config=mock.Mock(), registry=mock.Mock()),
                0,
            )
        tmux_service_cls.assert_not_called()

    def test_skips_when_message_is_missing(self) -> None:
        args = mock.Mock(payload='{"type":"agent-turn-complete"}')
        with mock.patch("co_agent.main.TmuxService") as tmux_service_cls:
            self.assertEqual(
                run_codex_notify(args, config=mock.Mock(), registry=mock.Mock()),
                0,
            )
        tmux_service_cls.assert_not_called()

    def test_sends_last_assistant_message_when_flag_enabled(self) -> None:
        args = mock.Mock(
            payload='{"type":"agent-turn-complete","last-assistant-message":"작업이 끝났습니다."}'
        )
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        send_result = mock.Mock(chunks_sent=1, channel_id=10, session_name="t1")

        with mock.patch("co_agent.main.TmuxService", return_value=tmux_service):
            with mock.patch("co_agent.main.send_to_session", return_value=send_result) as send:
                self.assertEqual(
                    run_codex_notify(args, config=mock.Mock(), registry=mock.Mock()),
                    0,
                )

        send.assert_called_once()

    def test_skips_when_notify_flag_is_disabled(self) -> None:
        args = mock.Mock(
            payload='{"type":"agent-turn-complete","last-assistant-message":"done"}'
        )
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = None

        with mock.patch("co_agent.main.TmuxService", return_value=tmux_service):
            with mock.patch("co_agent.main.send_to_session") as send:
                self.assertEqual(
                    run_codex_notify(args, config=mock.Mock(), registry=mock.Mock()),
                    0,
                )

        send.assert_not_called()


class RunCodexPermissionRequestTest(unittest.TestCase):
    def test_sends_permission_request_message_when_flag_enabled(self) -> None:
        payload = """
        {
          "hook_event_name": "PermissionRequest",
          "tool_input": {
            "command": "git push origin main",
            "description": "Need network access"
          }
        }
        """
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        send_result = mock.Mock(chunks_sent=1, channel_id=10, session_name="t1")

        with mock.patch("sys.stdin", mock.Mock(read=mock.Mock(return_value=payload))):
            with mock.patch("co_agent.main.TmuxService", return_value=tmux_service):
                with mock.patch(
                    "co_agent.main.send_to_session", return_value=send_result
                ) as send:
                    self.assertEqual(
                        run_codex_permission_request(
                            config=mock.Mock(),
                            registry=mock.Mock(),
                        ),
                        0,
                    )

        send.assert_called_once()
        sent_message = send.call_args.kwargs["message"]
        self.assertIn("승인 요청이 필요합니다.", sent_message)
        self.assertIn("git push origin main", sent_message)
        self.assertIn("Need network access", sent_message)

    def test_skips_when_hook_event_name_differs(self) -> None:
        payload = '{"hook_event_name":"Other","tool_input":{"command":"echo hi"}}'
        with mock.patch("sys.stdin", mock.Mock(read=mock.Mock(return_value=payload))):
            with mock.patch("co_agent.main.TmuxService") as tmux_service_cls:
                self.assertEqual(
                    run_codex_permission_request(
                        config=mock.Mock(),
                        registry=mock.Mock(),
                    ),
                    0,
                )
        tmux_service_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
