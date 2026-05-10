from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from tetherly.config import USER_CONFIG_DIR, USER_ENV_PATH

HOOK_STATUS_MESSAGE_STOP = "sending turn-complete notice to Discord"
HOOK_STATUS_MESSAGE_PERMISSION = "sending permission request to Discord"
HOOK_STATUS_MESSAGE_CLAUDE_STOP = "sending turn-complete notice to chat"
HOOK_STATUS_MESSAGE_CLAUDE_NOTIFICATION = "sending Claude Code notification to chat"


@dataclass(frozen=True)
class HookInstallResult:
    config_toml_path: Path
    hooks_json_path: Path
    config_toml_changed: bool
    hooks_json_changed: bool
    config_toml_diff: str | None
    hooks_json_diff: str | None


@dataclass(frozen=True)
class ClaudeHookInstallResult:
    settings_path: Path
    settings_changed: bool
    settings_diff: str | None


def _unified_diff(path: Path, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"{path} (before)",
            tofile=f"{path} (after)",
            n=3,
        )
    )


def resolve_tetherly_executable() -> str:
    """Return the `tetherly` CLI name for use in portable hook commands."""
    return "tetherly"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a `.env` file into a `key -> value` dict. Returns `{}` if missing."""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("'").strip('"')
    return result


def write_env_file(
    *,
    path: Path,
    discord_token: str | None = None,
    discord_user_ids: list[int] | None = None,
    discord_guild_id: int | None = None,
    discord_test_guild_id: int | None = None,
    telegram_token: str | None = None,
    telegram_user_ids: list[int] | None = None,
    telegram_chat_ids: list[int] | None = None,
    overwrite_backup: bool = True,
) -> bool:
    """Write a `.env` file with the supplied values. Backs up an existing file to `.bak`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists()
    if existed and overwrite_backup:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)

    lines: list[str] = []
    if discord_token:
        lines.append(f"DISCORD_BOT_TOKEN={discord_token}")
        if discord_user_ids:
            lines.append(
                f"TETHERLY_ALLOWED_USER_IDS={','.join(str(uid) for uid in discord_user_ids)}"
            )
        if discord_guild_id is not None:
            lines.append(f"TETHERLY_ALLOWED_GUILD_IDS={discord_guild_id}")
        if discord_test_guild_id is not None:
            lines.append(f"TETHERLY_TEST_GUILD_ID={discord_test_guild_id}")
    if telegram_token:
        lines.append(f"TELEGRAM_BOT_TOKEN={telegram_token}")
        if telegram_user_ids:
            lines.append(
                f"TETHERLY_TELEGRAM_ALLOWED_USER_IDS={','.join(str(uid) for uid in telegram_user_ids)}"
            )
        if telegram_chat_ids:
            lines.append(
                f"TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS={','.join(str(cid) for cid in telegram_chat_ids)}"
            )
    path.write_text("\n".join(lines) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return existed


def _load_codex_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _compute_codex_hooks_flag_text(text: str) -> str:
    features_match = re.search(r"^\s*\[features\]\s*$", text, re.MULTILINE)
    if features_match is None:
        suffix = "" if text.endswith("\n") else "\n"
        return f"{text}{suffix}\n[features]\ncodex_hooks = true\n"

    existing_flag = re.search(
        r"^[ \t]*codex_hooks[ \t]*=[ \t]*(true|false)[ \t]*$",
        text[features_match.end():],
        re.MULTILINE,
    )
    if existing_flag is not None:
        absolute_start = features_match.end() + existing_flag.start()
        absolute_end = features_match.end() + existing_flag.end()
        return text[:absolute_start] + "codex_hooks = true" + text[absolute_end:]

    insert_at = features_match.end()
    return text[:insert_at] + "\ncodex_hooks = true" + text[insert_at:]


def _ensure_codex_hooks_flag(path: Path) -> tuple[bool, str | None]:
    """Make sure `[features] codex_hooks = true` is set.

    Returns `(changed, diff)`. `diff` is a unified diff string when an existing
    file was modified; `None` when the file was newly created or unchanged.
    """
    data = _load_codex_config(path)
    if data.get("features", {}).get("codex_hooks") is True:
        return (False, None)

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[features]\ncodex_hooks = true\n")
        return (True, None)

    before = path.read_text()
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)

    after = _compute_codex_hooks_flag_text(before)
    path.write_text(after)
    return (True, _unified_diff(path, before, after))


def _hook_entry(executable: str, subcommand: str, status_message: str) -> dict:
    return {
        "hooks": [
            {
                "type": "command",
                "command": f"{executable} {subcommand}",
                "statusMessage": status_message,
            }
        ]
    }


def _entry_uses_subcommand(entry: dict, subcommand: str) -> bool:
    for hook in entry.get("hooks", []) or []:
        command = hook.get("command", "")
        if isinstance(command, str) and subcommand in command.split():
            return True
    return False


def _merge_hook_event(existing: list[dict], new_entry: dict, subcommand: str) -> list[dict]:
    filtered = [entry for entry in existing if not _entry_uses_subcommand(entry, subcommand)]
    filtered.append(new_entry)
    return filtered


def _ensure_codex_hooks_json(path: Path, executable: str) -> tuple[bool, str | None]:
    stop_entry = _hook_entry(executable, "codex-stop", HOOK_STATUS_MESSAGE_STOP)
    permission_entry = _hook_entry(
        executable, "codex-permission-request", HOOK_STATUS_MESSAGE_PERMISSION
    )

    before_text: str | None
    if path.exists():
        before_text = path.read_text()
        try:
            data = json.loads(before_text or "{}")
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
    else:
        before_text = None
        data = {}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    new_stop = _merge_hook_event(
        list(hooks.get("Stop") or []), stop_entry, "codex-stop"
    )
    new_permission = _merge_hook_event(
        list(hooks.get("PermissionRequest") or []),
        permission_entry,
        "codex-permission-request",
    )

    serialized_before = json.dumps(data, sort_keys=True) if before_text is not None else None
    hooks["Stop"] = new_stop
    hooks["PermissionRequest"] = new_permission
    serialized_after = json.dumps(data, sort_keys=True)

    if serialized_before == serialized_after:
        return (False, None)

    after_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    if before_text is not None:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
    path.write_text(after_text)

    if before_text is None:
        return (True, None)
    return (True, _unified_diff(path, before_text, after_text))


def install_codex_hooks(*, scope: str, executable: str | None = None) -> HookInstallResult:
    """Install user-level (`global`) or project-level (`project`) Codex hooks."""
    if scope not in ("global", "project"):
        raise ValueError(f"unknown scope: {scope!r}")

    if scope == "global":
        codex_dir = Path.home() / ".codex"
    else:
        codex_dir = Path.cwd() / ".codex"

    config_path = codex_dir / "config.toml"
    hooks_path = codex_dir / "hooks.json"
    exe = executable or resolve_tetherly_executable()

    config_changed, config_diff = _ensure_codex_hooks_flag(config_path)
    hooks_changed, hooks_diff = _ensure_codex_hooks_json(hooks_path, exe)
    return HookInstallResult(
        config_toml_path=config_path,
        hooks_json_path=hooks_path,
        config_toml_changed=config_changed,
        hooks_json_changed=hooks_changed,
        config_toml_diff=config_diff,
        hooks_json_diff=hooks_diff,
    )


def _ensure_claude_settings_json(path: Path, executable: str) -> tuple[bool, str | None]:
    """Merge tetherly's Stop and Notification handlers into a Claude Code settings.json.

    Claude Code reads hooks from `settings.json` (no separate feature flag needed).
    Existing top-level keys, other event keys, and entries that point at other
    commands are preserved.
    """
    stop_entry = _hook_entry(executable, "claude-stop", HOOK_STATUS_MESSAGE_CLAUDE_STOP)
    notification_entry = _hook_entry(
        executable, "claude-notification", HOOK_STATUS_MESSAGE_CLAUDE_NOTIFICATION
    )

    before_text: str | None
    if path.exists():
        before_text = path.read_text()
        try:
            data = json.loads(before_text or "{}")
        except json.JSONDecodeError:
            data = {}
        if not isinstance(data, dict):
            data = {}
    else:
        before_text = None
        data = {}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    new_stop = _merge_hook_event(
        list(hooks.get("Stop") or []), stop_entry, "claude-stop"
    )
    new_notification = _merge_hook_event(
        list(hooks.get("Notification") or []),
        notification_entry,
        "claude-notification",
    )

    serialized_before = json.dumps(data, sort_keys=True) if before_text is not None else None
    hooks["Stop"] = new_stop
    hooks["Notification"] = new_notification
    serialized_after = json.dumps(data, sort_keys=True)

    if serialized_before == serialized_after:
        return (False, None)

    after_text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    if before_text is not None:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
    path.write_text(after_text)

    if before_text is None:
        return (True, None)
    return (True, _unified_diff(path, before_text, after_text))


def install_claude_hooks(
    *, scope: str, executable: str | None = None
) -> ClaudeHookInstallResult:
    """Install user-level (`global`) or project-level (`project`) Claude Code hooks."""
    if scope not in ("global", "project"):
        raise ValueError(f"unknown scope: {scope!r}")

    if scope == "global":
        claude_dir = Path.home() / ".claude"
    else:
        claude_dir = Path.cwd() / ".claude"

    settings_path = claude_dir / "settings.json"
    exe = executable or resolve_tetherly_executable()

    changed, diff = _ensure_claude_settings_json(settings_path, exe)
    return ClaudeHookInstallResult(
        settings_path=settings_path,
        settings_changed=changed,
        settings_diff=diff,
    )


def ensure_user_config_dir() -> Path:
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return USER_CONFIG_DIR


__all__ = [
    "ClaudeHookInstallResult",
    "HookInstallResult",
    "USER_ENV_PATH",
    "ensure_user_config_dir",
    "install_claude_hooks",
    "install_codex_hooks",
    "read_env_file",
    "resolve_tetherly_executable",
    "write_env_file",
]
