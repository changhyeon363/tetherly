from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from co_agent.authz import AccessController
from co_agent.config import Config, load_dotenv
from co_agent.discord_bot import CoAgentBot
from co_agent.discord_sender import DiscordSendError, send_to_session
from co_agent.session_registry import SessionRegistry
from co_agent.tmux_service import TmuxService


def _append_hook_log(name: str, payload: object) -> None:
    log_dir = Path.cwd() / ".codex" / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / f"{name}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="co-agent")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run-bot", help="run the Discord bot")

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

    codex_notify = subparsers.add_parser(
        "codex-notify",
        help="handle Codex notify payloads and forward selected messages to Discord",
    )
    codex_notify.add_argument("payload", help="JSON payload from Codex notify")

    subparsers.add_parser(
        "codex-permission-request",
        help="handle Codex permission request hook payloads from standard input",
    )
    return parser


def run_bot(config: Config, registry: SessionRegistry) -> None:
    tmux_service = TmuxService()
    access_controller = AccessController(
        allowed_guild_ids=config.allowed_guild_ids,
        allowed_role_ids=config.allowed_role_ids,
        allowed_user_ids=config.allowed_user_ids,
    )

    bot = CoAgentBot(
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


def run_codex_notify(
    args: argparse.Namespace,
    *,
    config: Config,
    registry: SessionRegistry,
) -> int:
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        print(f"Invalid notify payload: {exc}", file=sys.stderr)
        return 2

    if payload.get("type") != "agent-turn-complete":
        return 0

    _append_hook_log("notify", payload)

    message = payload.get("last-assistant-message")
    if not isinstance(message, str) or not message.strip():
        return 0

    tmux_service = TmuxService()
    current_session = tmux_service.get_current_session_name()
    if current_session is None:
        return 0

    notify_flag = tmux_service.get_session_environment(
        current_session,
        "CO_AGENT_NOTIFY_ON_FINISH",
    )
    if notify_flag != "1":
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
        return 1

    print(
        f"Sent {result.chunks_sent} message chunk(s) to channel {result.channel_id} for session {result.session_name}."
    )
    return 0


def run_codex_permission_request(
    *,
    config: Config,
    registry: SessionRegistry,
) -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"Invalid permission request payload: {exc}", file=sys.stderr)
        return 2

    if payload.get("hook_event_name") != "PermissionRequest":
        return 0

    _append_hook_log("permission-request", payload)

    tmux_service = TmuxService()
    current_session = tmux_service.get_current_session_name()
    if current_session is None:
        return 0

    notify_flag = tmux_service.get_session_environment(
        current_session,
        "CO_AGENT_NOTIFY_ON_FINISH",
    )
    if notify_flag != "1":
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return 0

    description = tool_input.get("description")
    message = f"승인 요청이 필요합니다.\nCommand: {command.strip()}"
    if isinstance(description, str) and description.strip():
        message = f"{message}\nReason: {description.strip()}"

    try:
        result = send_to_session(
            config=config,
            registry=registry,
            session_name=current_session,
            message=message,
        )
    except DiscordSendError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"Sent {result.chunks_sent} message chunk(s) to channel {result.channel_id} for session {result.session_name}."
    )
    return 0


def resolve_session_name(
    session_arg: str | None,
    *,
    tmux_service: TmuxService,
) -> str | None:
    if session_arg:
        return session_arg
    env_session = os.environ.get("CO_AGENT_SESSION")
    if env_session:
        return env_session
    current_session = tmux_service.get_current_session_name()
    if current_session is None:
        return None
    tmux_env_session = tmux_service.get_session_environment(
        current_session,
        "CO_AGENT_SESSION",
    )
    if tmux_env_session:
        return tmux_env_session
    return current_session


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    config = Config.from_env()
    config.configure_logging()
    registry = SessionRegistry(config.state_path)
    if args.command in (None, "run-bot"):
        run_bot(config, registry)
        return
    if args.command == "discord-send":
        raise SystemExit(run_discord_send(args, config=config, registry=registry))
    if args.command == "codex-notify":
        raise SystemExit(run_codex_notify(args, config=config, registry=registry))
    if args.command == "codex-permission-request":
        raise SystemExit(run_codex_permission_request(config=config, registry=registry))
