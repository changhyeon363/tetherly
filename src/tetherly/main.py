from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys

from tetherly.authz import AccessController
from tetherly.config import Config, USER_ENV_PATH, load_dotenv
from tetherly.discord_bot import TetherlyBot
from tetherly.discord_sender import DiscordSendError, send_to_session
from tetherly.session_registry import SessionRegistry
from tetherly.setup import (
    ensure_user_config_dir,
    install_codex_hooks,
    write_env_file,
)
from tetherly.tmux_service import TmuxService


def _append_hook_log(name: str, payload: object) -> None:
    log_dir = Path.cwd() / ".codex" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / f"{name}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tetherly")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run-bot", help="run the Discord bot")

    init_parser = subparsers.add_parser(
        "init", help="interactive setup: write ~/.tetherly/.env and (optionally) Codex hooks"
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing files without prompting (a .bak is still kept)",
    )

    install_hooks_parser = subparsers.add_parser(
        "install-hooks",
        help="install Codex hooks for this project (or with --global, user-level)",
    )
    install_hooks_parser.add_argument(
        "--global",
        dest="global_scope",
        action="store_true",
        help="install hooks at ~/.codex/ instead of ./.codex/",
    )

    discord_send = subparsers.add_parser(
        "discord-send",
        help="send a message to the Discord channel bound to a tmux session",
    )
    discord_send.add_argument("--session", help="tmux session name")
    discord_send.add_argument("--message", help="message text to send")
    discord_send.add_argument(
        "--stdin",
        action="store_true",
        help="read the message body from standard input",
    )

    subparsers.add_parser(
        "codex-stop",
        help="handle Codex Stop hook payloads from standard input",
    )

    subparsers.add_parser(
        "codex-permission-request",
        help="handle Codex PermissionRequest hook payloads from standard input",
    )
    return parser


def _prompt(message: str, *, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        try:
            value = input(f"{message}{suffix}: ").strip()
        except EOFError:
            return default or ""
        if value:
            return value
        if default is not None:
            return default
        print("Please enter a value.")


def _prompt_optional(message: str) -> str:
    try:
        return input(f"{message} (optional, press Enter to skip): ").strip()
    except EOFError:
        return ""


def _prompt_int_list(message: str) -> list[int]:
    while True:
        raw = _prompt(message)
        try:
            values = [int(chunk.strip()) for chunk in raw.split(",") if chunk.strip()]
        except ValueError:
            print("  ✗ Expected comma-separated integers (e.g. 123,456). Try again.")
            continue
        if not values:
            print("  ✗ At least one ID is required.")
            continue
        return values


def _prompt_optional_int(message: str) -> int | None:
    raw = _prompt_optional(message)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print("  ✗ Not a valid integer; skipping.")
        return None


def _prompt_choice(message: str, choices: dict[str, str], default: str) -> str:
    print(message)
    for key, label in choices.items():
        marker = "*" if key == default else " "
        print(f"  [{key}]{marker} {label}")
    while True:
        try:
            raw = input(f"Choice [{default}]: ").strip().lower()
        except EOFError:
            return default
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"  ✗ Pick one of: {', '.join(choices)}")


def run_init(args: argparse.Namespace) -> int:
    print("tetherly — initial setup\n")
    print("This creates ~/.tetherly/.env and (optionally) installs Codex hooks.\n")

    if USER_ENV_PATH.exists() and not args.force:
        print(f"⚠  {USER_ENV_PATH} already exists.")
        proceed = _prompt_choice(
            "Overwrite it? (a .bak backup will be kept)",
            {"y": "yes, overwrite", "n": "no, abort"},
            default="n",
        )
        if proceed != "y":
            print("Aborted.")
            return 1

    print("Discord bot token (input hidden):")
    print("  → https://discord.com/developers/applications")
    try:
        token = getpass.getpass("  Token: ").strip()
    except EOFError:
        token = ""
    if not token:
        print("  ✗ Token is required.")
        return 2

    print("\nYour Discord user ID(s), comma-separated:")
    print("  → Discord settings → Advanced → Developer Mode, then right-click your name → Copy User ID.")
    user_ids = _prompt_int_list("  User ID(s)")

    print("\nOptional restrictions:")
    guild_id = _prompt_optional_int("  Discord server (guild) ID")
    test_guild_id = _prompt_optional_int("  Dev/test guild ID for fast slash-command sync")

    print()
    scope = _prompt_choice(
        "Where should Codex hooks be installed?",
        {
            "g": "Global  — once at ~/.codex/, fires in every project",
            "p": "Project — install per project later via `tetherly install-hooks`",
            "s": "Skip    — don't touch Codex hooks now",
        },
        default="g",
    )

    ensure_user_config_dir()
    existed = write_env_file(
        path=USER_ENV_PATH,
        token=token,
        user_ids=user_ids,
        guild_id=guild_id,
        test_guild_id=test_guild_id,
    )
    print()
    print(f"✓ {'Updated' if existed else 'Wrote'} {USER_ENV_PATH}")

    if scope == "g":
        result = install_codex_hooks(scope="global")
        if result.config_toml_changed:
            print(f"✓ Enabled codex_hooks in {result.config_toml_path}")
        else:
            print(f"· codex_hooks already enabled in {result.config_toml_path}")
        if result.hooks_json_changed:
            print(f"✓ Updated {result.hooks_json_path}")
        else:
            print(f"· {result.hooks_json_path} already up to date")

    print("\nNext steps:")
    print("  1. Start the bot:        tetherly")
    print("  2. In a Discord channel: /bind session:<your-tmux-session>")
    if scope == "p":
        print("  3. In each project:      tetherly install-hooks")
    return 0


def run_install_hooks(args: argparse.Namespace) -> int:
    scope = "global" if args.global_scope else "project"
    result = install_codex_hooks(scope=scope)
    where = "user-level (~/.codex/)" if scope == "global" else f"project ({Path.cwd()}/.codex/)"
    print(f"Codex hooks installed at {where}")
    if result.config_toml_changed:
        print(f"  ✓ {result.config_toml_path}: enabled codex_hooks")
    else:
        print(f"  · {result.config_toml_path}: already enabled")
    if result.hooks_json_changed:
        print(f"  ✓ {result.hooks_json_path}: registered Stop and PermissionRequest")
    else:
        print(f"  · {result.hooks_json_path}: already up to date")
    return 0


def run_bot(config: Config, registry: SessionRegistry) -> None:
    tmux_service = TmuxService()
    access_controller = AccessController(
        allowed_guild_ids=config.allowed_guild_ids,
        allowed_role_ids=config.allowed_role_ids,
        allowed_user_ids=config.allowed_user_ids,
    )

    bot = TetherlyBot(
        config=config,
        registry=registry,
        tmux_service=tmux_service,
        access_controller=access_controller,
    )
    bot.run(config.discord_bot_token)


def run_discord_send(
    args: argparse.Namespace,
    *,
    config: Config,
    registry: SessionRegistry,
) -> int:
    if bool(args.stdin) == bool(args.message):
        print("Use exactly one of --message or --stdin.", file=sys.stderr)
        return 2
    message = sys.stdin.read() if args.stdin else args.message
    tmux_service = TmuxService()
    session_name = resolve_session_name(args.session, tmux_service=tmux_service)
    if session_name is None:
        print(
            "Could not resolve session. Pass --session or run this command inside a bound tmux session.",
            file=sys.stderr,
        )
        return 2
    try:
        result = send_to_session(
            config=config,
            registry=registry,
            session_name=session_name,
            message=message,
        )
    except DiscordSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"Sent {result.chunks_sent} message chunk(s) to channel {result.channel_id} for session {result.session_name}."
    )
    return 0


def _emit_empty_hook_output() -> None:
    sys.stdout.write("{}")


def _notify_session_for_hook(tmux_service: TmuxService) -> str | None:
    current_session = tmux_service.get_current_session_name()
    if current_session is None:
        return None
    notify_flag = tmux_service.get_session_environment(
        current_session,
        "TETHERLY_NOTIFY_ON_FINISH",
    )
    if notify_flag != "1":
        return None
    return current_session


def _format_permission_request_message(payload: dict) -> str | None:
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")

    lines = ["승인 요청이 필요합니다."]
    if isinstance(tool_name, str) and tool_name.strip():
        lines.append(f"Tool: {tool_name.strip()}")

    description: str | None = None
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        if isinstance(command, str) and command.strip():
            lines.append(f"Command: {command.strip()}")
        else:
            details = {k: v for k, v in tool_input.items() if k != "description"}
            if details:
                lines.append(f"Input: {json.dumps(details, ensure_ascii=False)}")
        raw_description = tool_input.get("description")
        if isinstance(raw_description, str) and raw_description.strip():
            description = raw_description.strip()

    if description:
        lines.append(f"Reason: {description}")

    if len(lines) == 1:
        return None
    return "\n".join(lines)


def run_codex_stop(
    *,
    config: Config,
    registry: SessionRegistry,
) -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"Invalid Stop payload: {exc}", file=sys.stderr)
        return 2

    event_name = payload.get("hook_event_name")
    if event_name is not None and event_name != "Stop":
        _emit_empty_hook_output()
        return 0

    _append_hook_log("stop", payload)

    message = payload.get("last_assistant_message")
    if not isinstance(message, str) or not message.strip():
        _emit_empty_hook_output()
        return 0

    tmux_service = TmuxService()
    current_session = _notify_session_for_hook(tmux_service)
    if current_session is None:
        _emit_empty_hook_output()
        return 0

    try:
        result = send_to_session(
            config=config,
            registry=registry,
            session_name=current_session,
            message=message,
        )
    except DiscordSendError as exc:
        print(str(exc), file=sys.stderr)
        _emit_empty_hook_output()
        return 1

    print(
        f"Sent {result.chunks_sent} message chunk(s) to channel {result.channel_id} for session {result.session_name}.",
        file=sys.stderr,
    )
    _emit_empty_hook_output()
    return 0


def run_codex_permission_request(
    *,
    config: Config,
    registry: SessionRegistry,
) -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"Invalid PermissionRequest payload: {exc}", file=sys.stderr)
        return 2

    event_name = payload.get("hook_event_name")
    if event_name is not None and event_name != "PermissionRequest":
        _emit_empty_hook_output()
        return 0

    _append_hook_log("permission-request", payload)

    message = _format_permission_request_message(payload)
    if message is None:
        _emit_empty_hook_output()
        return 0

    tmux_service = TmuxService()
    current_session = _notify_session_for_hook(tmux_service)
    if current_session is None:
        _emit_empty_hook_output()
        return 0

    try:
        result = send_to_session(
            config=config,
            registry=registry,
            session_name=current_session,
            message=message,
        )
    except DiscordSendError as exc:
        print(str(exc), file=sys.stderr)
        _emit_empty_hook_output()
        return 1

    print(
        f"Sent {result.chunks_sent} message chunk(s) to channel {result.channel_id} for session {result.session_name}.",
        file=sys.stderr,
    )
    _emit_empty_hook_output()
    return 0


def resolve_session_name(
    session_arg: str | None,
    *,
    tmux_service: TmuxService,
) -> str | None:
    if session_arg:
        return session_arg
    env_session = os.environ.get("TETHERLY_SESSION")
    if env_session:
        return env_session
    current_session = tmux_service.get_current_session_name()
    if current_session is None:
        return None
    tmux_env_session = tmux_service.get_session_environment(
        current_session,
        "TETHERLY_SESSION",
    )
    if tmux_env_session:
        return tmux_env_session
    return current_session


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        raise SystemExit(run_init(args))
    if args.command == "install-hooks":
        raise SystemExit(run_install_hooks(args))

    load_dotenv()
    config = Config.from_env()
    config.configure_logging()
    registry = SessionRegistry(config.state_path)
    if args.command in (None, "run-bot"):
        run_bot(config, registry)
        return
    if args.command == "discord-send":
        raise SystemExit(run_discord_send(args, config=config, registry=registry))
    if args.command == "codex-stop":
        raise SystemExit(run_codex_stop(config=config, registry=registry))
    if args.command == "codex-permission-request":
        raise SystemExit(run_codex_permission_request(config=config, registry=registry))
