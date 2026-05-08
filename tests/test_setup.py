from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tetherly.setup import install_codex_hooks, resolve_tetherly_executable


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


if __name__ == "__main__":
    unittest.main()
