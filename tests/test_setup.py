from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tetherly.setup import (
    install_claude_hooks,
    install_codex_hooks,
    resolve_tetherly_executable,
)


class ResolveTetherlyExecutableTest(unittest.TestCase):
    @mock.patch("tetherly.setup.shutil.which", return_value="/tmp/project/.venv/bin/tetherly")
    def test_uses_cli_name_instead_of_environment_specific_path(self, _: mock.Mock) -> None:
        self.assertEqual(resolve_tetherly_executable(), "tetherly")


class InstallCodexHooksTest(unittest.TestCase):
    @mock.patch("tetherly.setup.shutil.which", return_value="/tmp/project/.venv/bin/tetherly")
    def test_project_hooks_use_tetherly_command_name(self, _: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                result = install_codex_hooks(scope="project")

            data = json.loads(result.hooks_json_path.read_text())

        stop_command = data["hooks"]["Stop"][0]["hooks"][0]["command"]
        permission_command = data["hooks"]["PermissionRequest"][0]["hooks"][0]["command"]
        self.assertEqual(stop_command, "tetherly codex-stop")
        self.assertEqual(permission_command, "tetherly codex-permission-request")

    def test_flips_false_flag_to_true_without_breaking_toml(self) -> None:
        # Regression: the previous regex used `\s*` for the leading boundary,
        # which would consume the newline between `[features]` and the flag,
        # producing `[features]codex_hooks = true` on disk.
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            codex = project / ".codex"
            codex.mkdir()
            (codex / "config.toml").write_text(
                "[features]\ncodex_hooks = false\n\n[other]\nkey = 1\n"
            )
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                result = install_codex_hooks(scope="project")

            text = (codex / "config.toml").read_text()

        self.assertIn("[features]\ncodex_hooks = true", text)
        self.assertIn("[other]", text)
        self.assertIsNotNone(result.config_toml_diff)
        self.assertIn("-codex_hooks = false", result.config_toml_diff)
        self.assertIn("+codex_hooks = true", result.config_toml_diff)

    def test_diff_populated_when_stale_tetherly_entry_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            codex = project / ".codex"
            codex.mkdir()
            (codex / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "tetherly codex-stop",
                                            "statusMessage": "OLD",
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    indent=2,
                )
                + "\n"
            )
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                result = install_codex_hooks(scope="project")

        self.assertTrue(result.hooks_json_changed)
        self.assertIsNotNone(result.hooks_json_diff)
        self.assertIn("-", result.hooks_json_diff)
        self.assertIn('"OLD"', result.hooks_json_diff)
        self.assertIn(
            "sending turn-complete notice to Discord", result.hooks_json_diff
        )

    def test_diff_is_none_for_fresh_install_and_idempotent_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                first = install_codex_hooks(scope="project")
                second = install_codex_hooks(scope="project")

        # Fresh install: changed=True but no prior content to diff against.
        self.assertTrue(first.config_toml_changed)
        self.assertIsNone(first.config_toml_diff)
        self.assertTrue(first.hooks_json_changed)
        self.assertIsNone(first.hooks_json_diff)

        # Idempotent re-run: nothing changed, nothing to show.
        self.assertFalse(second.config_toml_changed)
        self.assertIsNone(second.config_toml_diff)
        self.assertFalse(second.hooks_json_changed)
        self.assertIsNone(second.hooks_json_diff)


class InstallClaudeHooksTest(unittest.TestCase):
    def test_project_hooks_use_tetherly_command_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                result = install_claude_hooks(scope="project")

            data = json.loads(result.settings_path.read_text())

        stop_command = data["hooks"]["Stop"][0]["hooks"][0]["command"]
        notification_command = data["hooks"]["Notification"][0]["hooks"][0]["command"]
        self.assertEqual(stop_command, "tetherly claude-stop")
        self.assertEqual(notification_command, "tetherly claude-notification")
        self.assertEqual(
            result.settings_path,
            project / ".claude" / "settings.json",
        )

    def test_global_scope_uses_home_claude_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            with mock.patch("tetherly.setup.Path.home", return_value=home):
                result = install_claude_hooks(scope="global")

            self.assertEqual(result.settings_path, home / ".claude" / "settings.json")
            self.assertTrue(result.settings_path.exists())

    def test_preserves_unrelated_keys_and_other_event_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            claude = project / ".claude"
            claude.mkdir()
            existing = {
                "permissions": {"allow": ["Bash(ls *)"]},
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "/usr/local/bin/audit"}],
                        }
                    ],
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": "/usr/local/bin/other-stop"}
                            ]
                        }
                    ],
                },
            }
            (claude / "settings.json").write_text(
                json.dumps(existing, indent=2) + "\n"
            )
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                result = install_claude_hooks(scope="project")

            data = json.loads((claude / "settings.json").read_text())

        self.assertTrue(result.settings_changed)
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls *)"]})
        self.assertIn("PreToolUse", data["hooks"])
        # Existing non-tetherly Stop entry survives alongside the new one.
        stop_commands = [
            hook["command"]
            for entry in data["hooks"]["Stop"]
            for hook in entry["hooks"]
        ]
        self.assertIn("/usr/local/bin/other-stop", stop_commands)
        self.assertIn("tetherly claude-stop", stop_commands)
        # Notification was added fresh.
        notification_commands = [
            hook["command"]
            for entry in data["hooks"]["Notification"]
            for hook in entry["hooks"]
        ]
        self.assertEqual(notification_commands, ["tetherly claude-notification"])

    def test_replaces_stale_tetherly_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            claude = project / ".claude"
            claude.mkdir()
            (claude / "settings.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "tetherly claude-stop",
                                            "statusMessage": "OLD",
                                        }
                                    ]
                                }
                            ]
                        }
                    },
                    indent=2,
                )
                + "\n"
            )
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                result = install_claude_hooks(scope="project")

        self.assertTrue(result.settings_changed)
        self.assertIsNotNone(result.settings_diff)
        self.assertIn('"OLD"', result.settings_diff)

    def test_diff_is_none_for_fresh_install_and_idempotent_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            with mock.patch("tetherly.setup.Path.cwd", return_value=project):
                first = install_claude_hooks(scope="project")
                second = install_claude_hooks(scope="project")

        self.assertTrue(first.settings_changed)
        self.assertIsNone(first.settings_diff)
        self.assertFalse(second.settings_changed)
        self.assertIsNone(second.settings_diff)


if __name__ == "__main__":
    unittest.main()
