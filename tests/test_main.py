from __future__ import annotations

import io
import os
import unittest
from unittest import mock

from tetherly.main import (
    resolve_session_name,
    run_claude_notification,
    run_claude_stop,
    run_codex_permission_request,
    run_codex_stop,
)
from tetherly.telegram_bot import MessageIntent


class ResolveSessionNameTest(unittest.TestCase):
    def test_prefers_explicit_session(self) -> None:
        tmux_service = mock.Mock()
        self.assertEqual(
            resolve_session_name("t1", tmux_service=tmux_service),
            "t1",
        )

    @mock.patch.dict(os.environ, {"TETHERLY_SESSION": "from-env"}, clear=False)
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


class RunCodexStopTest(unittest.TestCase):
    def _stdin(self, text: str) -> mock.Mock:
        return mock.patch("sys.stdin", io.StringIO(text))

    def test_sends_last_assistant_message_when_flag_enabled(self) -> None:
        payload = '{"hook_event_name":"Stop","last_assistant_message":"작업이 끝났습니다."}'
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch(
            "tetherly.main.route_to_session", return_value=("discord", 10, 1)
        ) as route:
            self.assertEqual(
                run_codex_stop(config=mock.Mock(), registry=mock.Mock()),
                0,
            )

        route.assert_called_once()
        self.assertEqual(route.call_args.kwargs["intent"], MessageIntent.STOP)
        self.assertEqual(stdout.getvalue(), "{}")

    def test_skips_when_message_is_missing(self) -> None:
        payload = '{"hook_event_name":"Stop"}'
        stdout = io.StringIO()
        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService"
        ) as tmux_service_cls:
            self.assertEqual(
                run_codex_stop(config=mock.Mock(), registry=mock.Mock()),
                0,
            )
        tmux_service_cls.assert_not_called()
        self.assertEqual(stdout.getvalue(), "{}")

    def test_skips_when_notify_flag_is_disabled(self) -> None:
        payload = '{"hook_event_name":"Stop","last_assistant_message":"done"}'
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = None
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch("tetherly.main.route_to_session") as route:
            self.assertEqual(
                run_codex_stop(config=mock.Mock(), registry=mock.Mock()),
                0,
            )

        route.assert_not_called()
        self.assertEqual(stdout.getvalue(), "{}")


class RunCodexPermissionRequestTest(unittest.TestCase):
    def _stdin(self, text: str) -> mock.Mock:
        return mock.patch("sys.stdin", io.StringIO(text))

    def test_sends_permission_request_message_when_flag_enabled(self) -> None:
        payload = """
        {
          "hook_event_name": "PermissionRequest",
          "tool_name": "Bash",
          "tool_input": {
            "command": "git push origin main",
            "description": "Need network access"
          }
        }
        """
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch(
            "tetherly.main.route_to_session", return_value=("telegram", 555, 1)
        ) as route:
            self.assertEqual(
                run_codex_permission_request(
                    config=mock.Mock(),
                    registry=mock.Mock(),
                ),
                0,
            )

        route.assert_called_once()
        sent_message = route.call_args.kwargs["message"]
        self.assertEqual(route.call_args.kwargs["intent"], MessageIntent.PERMISSION)
        self.assertIn("승인 요청이 필요합니다.", sent_message)
        self.assertIn("Tool: Bash", sent_message)
        self.assertIn("git push origin main", sent_message)
        self.assertIn("Need network access", sent_message)
        self.assertEqual(stdout.getvalue(), "{}")

    def test_formats_mcp_tool_input_when_command_missing(self) -> None:
        payload = (
            '{"hook_event_name":"PermissionRequest",'
            '"tool_name":"mcp__fs__read",'
            '"tool_input":{"path":"/etc/passwd","description":"read host file"}}'
        )
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch(
            "tetherly.main.route_to_session", return_value=("discord", 10, 1)
        ) as route:
            self.assertEqual(
                run_codex_permission_request(
                    config=mock.Mock(),
                    registry=mock.Mock(),
                ),
                0,
            )

        sent_message = route.call_args.kwargs["message"]
        self.assertIn("Tool: mcp__fs__read", sent_message)
        self.assertIn('"path": "/etc/passwd"', sent_message)
        self.assertIn("read host file", sent_message)

    def test_skips_when_hook_event_name_differs(self) -> None:
        payload = '{"hook_event_name":"Other","tool_input":{"command":"echo hi"}}'
        stdout = io.StringIO()
        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService"
        ) as tmux_service_cls:
            self.assertEqual(
                run_codex_permission_request(
                    config=mock.Mock(),
                    registry=mock.Mock(),
                ),
                0,
            )
        tmux_service_cls.assert_not_called()
        self.assertEqual(stdout.getvalue(), "{}")


class RunClaudeStopTest(unittest.TestCase):
    def _stdin(self, text: str) -> mock.Mock:
        return mock.patch("sys.stdin", io.StringIO(text))

    def test_sends_last_assistant_message_when_flag_enabled(self) -> None:
        payload = (
            '{"hook_event_name":"Stop",'
            '"last_assistant_message":"작업이 끝났습니다."}'
        )
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch(
            "tetherly.main.route_to_session", return_value=("discord", 10, 1)
        ) as route:
            self.assertEqual(
                run_claude_stop(config=mock.Mock(), registry=mock.Mock()),
                0,
            )

        route.assert_called_once()
        self.assertEqual(route.call_args.kwargs["intent"], MessageIntent.STOP)
        self.assertEqual(stdout.getvalue(), "{}")

    def test_skips_when_stop_hook_active(self) -> None:
        payload = (
            '{"hook_event_name":"Stop",'
            '"stop_hook_active":true,'
            '"last_assistant_message":"already continuing"}'
        )
        stdout = io.StringIO()
        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService"
        ) as tmux_service_cls:
            self.assertEqual(
                run_claude_stop(config=mock.Mock(), registry=mock.Mock()),
                0,
            )
        tmux_service_cls.assert_not_called()
        self.assertEqual(stdout.getvalue(), "{}")

    def test_skips_when_event_name_differs(self) -> None:
        payload = (
            '{"hook_event_name":"PostToolUse",'
            '"last_assistant_message":"unrelated"}'
        )
        stdout = io.StringIO()
        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService"
        ) as tmux_service_cls:
            self.assertEqual(
                run_claude_stop(config=mock.Mock(), registry=mock.Mock()),
                0,
            )
        tmux_service_cls.assert_not_called()
        self.assertEqual(stdout.getvalue(), "{}")


class RunClaudeNotificationTest(unittest.TestCase):
    def _stdin(self, text: str) -> mock.Mock:
        return mock.patch("sys.stdin", io.StringIO(text))

    def test_routes_permission_prompt_with_permission_intent(self) -> None:
        payload = (
            '{"hook_event_name":"Notification",'
            '"notification_type":"permission_prompt",'
            '"message":"Claude needs your permission to use Bash"}'
        )
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch(
            "tetherly.main.route_to_session", return_value=("telegram", 555, 1)
        ) as route:
            self.assertEqual(
                run_claude_notification(config=mock.Mock(), registry=mock.Mock()),
                0,
            )

        route.assert_called_once()
        sent_message = route.call_args.kwargs["message"]
        self.assertEqual(route.call_args.kwargs["intent"], MessageIntent.PERMISSION)
        self.assertIn("permission_prompt", sent_message)
        self.assertIn("Claude needs your permission to use Bash", sent_message)
        self.assertEqual(stdout.getvalue(), "{}")

    def test_routes_idle_prompt_with_plain_intent(self) -> None:
        payload = (
            '{"hook_event_name":"Notification",'
            '"notification_type":"idle_prompt",'
            '"message":"Claude is waiting for your input"}'
        )
        tmux_service = mock.Mock()
        tmux_service.get_current_session_name.return_value = "t1"
        tmux_service.get_session_environment.return_value = "1"
        stdout = io.StringIO()

        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService", return_value=tmux_service
        ), mock.patch(
            "tetherly.main.route_to_session", return_value=("discord", 10, 1)
        ) as route:
            self.assertEqual(
                run_claude_notification(config=mock.Mock(), registry=mock.Mock()),
                0,
            )

        self.assertEqual(route.call_args.kwargs["intent"], MessageIntent.PLAIN)
        sent_message = route.call_args.kwargs["message"]
        self.assertIn("idle_prompt", sent_message)
        self.assertIn("Claude is waiting for your input", sent_message)

    def test_skips_when_message_is_blank(self) -> None:
        payload = '{"hook_event_name":"Notification","message":"   "}'
        stdout = io.StringIO()
        with self._stdin(payload), mock.patch("sys.stdout", stdout), mock.patch(
            "tetherly.main.TmuxService"
        ) as tmux_service_cls:
            self.assertEqual(
                run_claude_notification(config=mock.Mock(), registry=mock.Mock()),
                0,
            )
        tmux_service_cls.assert_not_called()
        self.assertEqual(stdout.getvalue(), "{}")


if __name__ == "__main__":
    unittest.main()
