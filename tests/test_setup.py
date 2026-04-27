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


if __name__ == "__main__":
    unittest.main()
