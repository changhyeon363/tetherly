from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import shlex
import subprocess
from pathlib import Path
import sys

from tetherly.authz import AccessController
from tetherly.config import Config, ConfigError, USER_ENV_PATH, load_dotenv
from tetherly.discord_bot import TetherlyBot, components_for_intent
from tetherly.discord_sender import (
    DiscordSendError,
    SendResult,
    send_to_session_async as discord_send_to_session_async,
)
from tetherly.models import PLATFORM_DISCORD, PLATFORM_TELEGRAM, ChannelBinding
from tetherly.session_registry import SessionRegistry
from tetherly.setup import (
    ensure_user_config_dir,
    install_codex_hooks,
    read_env_file,
    write_env_file,
)
from tetherly.telegram_bot import (
    MessageIntent,
    TelegramAccessController,
    TelegramBot,
    keyboard_for_intent,
)
from tetherly.telegram_sender import (
    TelegramSendError,
    TelegramSendResult,
    send_to_session_async as telegram_send_to_session_async,
)
from tetherly.tmux_service import TmuxService


class RoutingError(RuntimeError):
    pass


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

    subparsers.add_parser("run-bot", help="run the configured chat bots")

    init_parser = subparsers.add_parser(
        "init", help="interactive setup: write ~/.tetherly/.env and (optionally) Codex hooks"
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing files without prompting (a .bak is still kept)",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="show or edit ~/.tetherly/.env",
    )
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("show", help="print current config (token masked)")
    config_sub.add_parser("edit", help="open ~/.tetherly/.env in $EDITOR")

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

    send_parser = subparsers.add_parser(
        "send",
        help="send a message to whichever chat (Discord/Telegram) is bound to a tmux session",
    )
    send_parser.add_argument("--session", help="tmux session name")
    send_parser.add_argument("--message", help="message text to send")
    send_parser.add_argument(
        "--stdin",
        action="store_true",
        help="read the message body from standard input",
    )

    # Backwards-compatible aliases
    discord_send_parser = subparsers.add_parser(
        "discord-send",
        help="alias for `tetherly send` (kept for backward compatibility)",
    )
    discord_send_parser.add_argument("--session")
    discord_send_parser.add_argument("--message")
    discord_send_parser.add_argument("--stdin", action="store_true")

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


def _prompt_optional(message: str, *, default: str = "") -> str:
    hint = default if default else "press Enter to skip"
    try:
        return input(f"{message} (optional, [{hint}]): ").strip()
    except EOFError:
        return ""


def _prompt_int_list(message: str, *, default: str = "") -> list[int]:
    while True:
        raw = _prompt(message, default=default or None)
        try:
            values = [int(chunk.strip()) for chunk in raw.split(",") if chunk.strip()]
        except ValueError:
            print("  ✗ Expected comma-separated integers (e.g. 123,456). Try again.")
            continue
        if not values:
            print("  ✗ At least one ID is required.")
            continue
        return values


def _prompt_optional_int_list(message: str, *, default: str = "") -> list[int]:
    raw = _prompt_optional(message, default=default)
    if not raw:
        if default:
            try:
                return [int(chunk.strip()) for chunk in default.split(",") if chunk.strip()]
            except ValueError:
                return []
        return []
    try:
        return [int(chunk.strip()) for chunk in raw.split(",") if chunk.strip()]
    except ValueError:
        print("  ✗ Not valid integers; skipping.")
        return []


def _prompt_optional_int(message: str, *, default: str = "") -> int | None:
    raw = _prompt_optional(message, default=default)
    if not raw:
        if default:
            try:
                return int(default)
            except ValueError:
                return None
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

    existing = read_env_file(USER_ENV_PATH)
    if existing and not args.force:
        print(f"⚠  {USER_ENV_PATH} already exists.")
        print("   Existing values are shown as defaults; press Enter to keep them.")
        proceed = _prompt_choice(
            "Update it? (a .bak backup will be kept)",
            {"y": "yes, update", "n": "no, abort"},
            default="y",
        )
        if proceed != "y":
            print("Aborted.")
            return 1

    print("Configure at least one of Discord, Telegram (or both).\n")

    enable_discord = _prompt_choice(
        "Enable Discord bot?",
        {"y": "yes", "n": "skip"},
        default="y" if existing.get("DISCORD_BOT_TOKEN") else "y",
    ) == "y"

    discord_token = ""
    discord_user_ids: list[int] = []
    discord_guild_id: int | None = None
    discord_test_guild_id: int | None = None
    if enable_discord:
        existing_token = existing.get("DISCORD_BOT_TOKEN", "").strip()
        print("\nDiscord bot token (input hidden):")
        print("  → https://discord.com/developers/applications")
        if existing_token:
            masked = "•" * 4 + existing_token[-4:] if len(existing_token) >= 4 else "••••"
            print(f"  Press Enter to keep existing token ({masked}).")
        try:
            discord_token = getpass.getpass("  Token: ").strip()
        except EOFError:
            discord_token = ""
        if not discord_token:
            if existing_token:
                discord_token = existing_token
            else:
                print("  ✗ Token is required.")
                return 2

        print("\nYour Discord user ID(s), comma-separated:")
        print("  → Discord settings → Advanced → Developer Mode, then right-click → Copy User ID.")
        discord_user_ids = _prompt_int_list(
            "  User ID(s)",
            default=existing.get("TETHERLY_ALLOWED_USER_IDS", ""),
        )

        print("\nOptional Discord restrictions:")
        discord_guild_id = _prompt_optional_int(
            "  Discord server (guild) ID",
            default=existing.get("TETHERLY_ALLOWED_GUILD_IDS", ""),
        )
        discord_test_guild_id = _prompt_optional_int(
            "  Dev/test guild ID for fast slash-command sync",
            default=existing.get("TETHERLY_TEST_GUILD_ID", ""),
        )

    enable_telegram = _prompt_choice(
        "\nEnable Telegram bot?",
        {"y": "yes", "n": "skip"},
        default="y" if existing.get("TELEGRAM_BOT_TOKEN") else "n",
    ) == "y"

    telegram_token = ""
    telegram_user_ids: list[int] = []
    telegram_chat_ids: list[int] = []
    if enable_telegram:
        existing_token = existing.get("TELEGRAM_BOT_TOKEN", "").strip()
        print("\nTelegram bot token (input hidden):")
        print("  → Talk to @BotFather on Telegram, run /newbot, copy the token.")
        if existing_token:
            masked = "•" * 4 + existing_token[-4:] if len(existing_token) >= 4 else "••••"
            print(f"  Press Enter to keep existing token ({masked}).")
        try:
            telegram_token = getpass.getpass("  Token: ").strip()
        except EOFError:
            telegram_token = ""
        if not telegram_token:
            if existing_token:
                telegram_token = existing_token
            else:
                print("  ✗ Token is required.")
                return 2

        print("\nYour Telegram user ID(s), comma-separated:")
        print("  → DM @userinfobot on Telegram to learn your numeric user ID.")
        telegram_user_ids = _prompt_int_list(
            "  User ID(s)",
            default=existing.get("TETHERLY_TELEGRAM_ALLOWED_USER_IDS", ""),
        )
        print("\nOptional Telegram restrictions:")
        print("  → Group/supergroup chat IDs are NEGATIVE (e.g. -1001234567890).")
        print("    Positive values only match private 1-on-1 DMs with the bot.")
        print("    To find a group's ID, forward a message from it to @JsonDumpBot.")
        telegram_chat_ids = _prompt_optional_int_list(
            "  Telegram chat ID(s) to allow (comma-separated; leave blank for any)",
            default=existing.get("TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS", ""),
        )
        if any(v > 0 for v in telegram_chat_ids):
            print(
                "  ⚠  One or more entries are positive — those only match private DMs."
            )
            print(
                "     If you meant a group, prepend a minus sign (e.g. -1001234567890)."
            )

    if not enable_discord and not enable_telegram:
        print("\n✗ At least one of Discord or Telegram must be enabled. Aborting.")
        return 2

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
        discord_token=discord_token or None,
        discord_user_ids=discord_user_ids,
        discord_guild_id=discord_guild_id,
        discord_test_guild_id=discord_test_guild_id,
        telegram_token=telegram_token or None,
        telegram_user_ids=telegram_user_ids,
        telegram_chat_ids=telegram_chat_ids,
    )
    print()
    print(f"✓ {'Updated' if existed else 'Wrote'} {USER_ENV_PATH}")

    if scope == "g":
        result = install_codex_hooks(scope="global")
        if result.config_toml_changed:
            print(f"✓ Enabled codex_hooks in {result.config_toml_path}")
            _print_install_diff(result.config_toml_diff, indent="  ")
        else:
            print(f"· codex_hooks already enabled in {result.config_toml_path}")
        if result.hooks_json_changed:
            print(f"✓ Updated {result.hooks_json_path}")
            _print_install_diff(result.hooks_json_diff, indent="  ")
        else:
            print(f"· {result.hooks_json_path} already up to date")

    print("\nNext steps:")
    print("  1. Start the bot:    tetherly")
    if enable_discord:
        print("  2. In Discord:       /bind session:<your-tmux-session>")
    if enable_telegram:
        print("  3. In Telegram:      /bind <your-tmux-session>")
    if scope == "p":
        print("  4. In each project:  tetherly install-hooks")
    return 0


def run_install_hooks(args: argparse.Namespace) -> int:
    scope = "global" if args.global_scope else "project"
    result = install_codex_hooks(scope=scope)
    where = "user-level (~/.codex/)" if scope == "global" else f"project ({Path.cwd()}/.codex/)"
    print(f"Codex hooks installed at {where}")
    if result.config_toml_changed:
        print(f"  ✓ {result.config_toml_path}: enabled codex_hooks")
        _print_install_diff(result.config_toml_diff, indent="    ")
    else:
        print(f"  · {result.config_toml_path}: already enabled")
    if result.hooks_json_changed:
        print(f"  ✓ {result.hooks_json_path}: registered Stop and PermissionRequest")
        _print_install_diff(result.hooks_json_diff, indent="    ")
    else:
        print(f"  · {result.hooks_json_path}: already up to date")
    return 0


def _print_install_diff(diff: str | None, *, indent: str) -> None:
    """Render a unified diff under the install command's `✓` line.

    `diff` is `None` for newly-created files (no prior content to compare against).
    """
    if not diff:
        return
    use_color = sys.stdout.isatty()
    for line in diff.splitlines():
        if use_color:
            if line.startswith("@@"):
                line = f"\x1b[36m{line}\x1b[0m"
            elif line.startswith("+++") or line.startswith("---"):
                line = f"\x1b[1m{line}\x1b[0m"
            elif line.startswith("+"):
                line = f"\x1b[32m{line}\x1b[0m"
            elif line.startswith("-"):
                line = f"\x1b[31m{line}\x1b[0m"
        print(f"{indent}{line}")


_CONFIG_KEY_ORDER = (
    "DISCORD_BOT_TOKEN",
    "TETHERLY_ALLOWED_USER_IDS",
    "TETHERLY_ALLOWED_GUILD_IDS",
    "TETHERLY_TEST_GUILD_ID",
    "TELEGRAM_BOT_TOKEN",
    "TETHERLY_TELEGRAM_ALLOWED_USER_IDS",
    "TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS",
)
_TOKEN_KEYS = {"DISCORD_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"}


def _mask_token(value: str) -> str:
    if not value:
        return "(unset)"
    return ("•" * 4) + value[-4:] if len(value) >= 4 else "••••"


def run_config_show() -> int:
    if not USER_ENV_PATH.exists():
        print(
            f"No config found at {USER_ENV_PATH}. Run `tetherly init` to create it.",
            file=sys.stderr,
        )
        return 1
    values = read_env_file(USER_ENV_PATH)
    print(f"Config: {USER_ENV_PATH}")
    seen: set[str] = set()
    for key in _CONFIG_KEY_ORDER:
        seen.add(key)
        raw = values.get(key, "")
        display = _mask_token(raw) if key in _TOKEN_KEYS else (raw or "(unset)")
        print(f"  {key}={display}")
    for key, raw in values.items():
        if key in seen:
            continue
        print(f"  {key}={raw}")
    raw_chat_ids = values.get("TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS", "")
    if raw_chat_ids:
        try:
            chat_ids = [int(c.strip()) for c in raw_chat_ids.split(",") if c.strip()]
        except ValueError:
            chat_ids = []
        if any(v > 0 for v in chat_ids):
            print(
                "\nNote: TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS contains positive IDs. "
                "Those only match private 1-on-1 DMs;"
            )
            print(
                "      Telegram group/supergroup chat IDs are NEGATIVE "
                "(e.g. -1001234567890)."
            )
    print("\nEdit with `tetherly config edit` or re-run `tetherly init`.")
    return 0


def run_config_edit() -> int:
    if not USER_ENV_PATH.exists():
        print(
            f"No config found at {USER_ENV_PATH}. Run `tetherly init` first.",
            file=sys.stderr,
        )
        return 1
    editor_cmd = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    argv = shlex.split(editor_cmd) + [str(USER_ENV_PATH)]
    try:
        return subprocess.call(argv)
    except FileNotFoundError:
        print(
            f"Could not launch editor {editor_cmd!r}. Set $EDITOR or edit {USER_ENV_PATH} directly.",
            file=sys.stderr,
        )
        return 1


def run_bot(config: Config, registry: SessionRegistry) -> None:
    asyncio.run(_run_bots(config, registry))


async def _run_bots(config: Config, registry: SessionRegistry) -> None:
    tmux_service = TmuxService()
    tasks: list[asyncio.Task] = []
    if config.discord_bot_token:
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
        tasks.append(asyncio.create_task(bot.start(config.discord_bot_token), name="discord"))
    if config.telegram_bot_token:
        telegram_access = TelegramAccessController(
            allowed_user_ids=config.telegram_allowed_user_ids,
            allowed_chat_ids=config.telegram_allowed_chat_ids,
        )
        telegram_bot = TelegramBot(
            config=config,
            registry=registry,
            tmux_service=tmux_service,
            access_controller=telegram_access,
        )
        tasks.append(asyncio.create_task(telegram_bot.run(), name="telegram"))
    if not tasks:
        raise RuntimeError("no chat bots configured")
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        raise


async def _send_message_to_binding(
    *,
    config: Config,
    registry: SessionRegistry,
    binding: ChannelBinding,
    message: str,
    intent: MessageIntent = MessageIntent.PLAIN,
) -> tuple[str, int, int]:
    """Send `message` to the channel a binding points to. Returns (platform, channel_id, chunks)."""
    if binding.platform == PLATFORM_DISCORD:
        if not config.discord_bot_token:
            raise RoutingError(
                f"binding for {binding.session_name!r} is Discord but DISCORD_BOT_TOKEN is unset"
            )
        result: SendResult = await discord_send_to_session_async(
            config=config,
            registry=registry,
            session_name=binding.session_name,
            message=message,
            components=components_for_intent(intent),
        )
        return PLATFORM_DISCORD, result.channel_id, result.chunks_sent
    if binding.platform == PLATFORM_TELEGRAM:
        if not config.telegram_bot_token:
            raise RoutingError(
                f"binding for {binding.session_name!r} is Telegram but TELEGRAM_BOT_TOKEN is unset"
            )
        result_tg: TelegramSendResult = await telegram_send_to_session_async(
            config=config,
            registry=registry,
            session_name=binding.session_name,
            message=message,
            reply_markup=keyboard_for_intent(intent),
        )
        return PLATFORM_TELEGRAM, result_tg.chat_id, result_tg.chunks_sent
    raise RoutingError(f"unknown platform {binding.platform!r}")


def route_to_session(
    *,
    config: Config,
    registry: SessionRegistry,
    session_name: str,
    message: str,
    intent: MessageIntent = MessageIntent.PLAIN,
) -> tuple[str, int, int]:
    binding = registry.get_by_session_name(session_name)
    if binding is None:
        raise RoutingError(f"no binding for session {session_name!r}")
    return asyncio.run(
        _send_message_to_binding(
            config=config,
            registry=registry,
            binding=binding,
            message=message,
            intent=intent,
        )
    )


def run_send(
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
        platform, target_id, chunks = route_to_session(
            config=config,
            registry=registry,
            session_name=session_name,
            message=message,
        )
    except (RoutingError, DiscordSendError, TelegramSendError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"Sent {chunks} message chunk(s) to {platform} target {target_id} for session {session_name}."
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
        platform, target_id, chunks = route_to_session(
            config=config,
            registry=registry,
            session_name=current_session,
            message=message,
            intent=MessageIntent.STOP,
        )
    except (RoutingError, DiscordSendError, TelegramSendError) as exc:
        print(str(exc), file=sys.stderr)
        _emit_empty_hook_output()
        return 1

    print(
        f"Sent {chunks} message chunk(s) to {platform} target {target_id} for session {current_session}.",
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
        platform, target_id, chunks = route_to_session(
            config=config,
            registry=registry,
            session_name=current_session,
            message=message,
            intent=MessageIntent.PERMISSION,
        )
    except (RoutingError, DiscordSendError, TelegramSendError) as exc:
        print(str(exc), file=sys.stderr)
        _emit_empty_hook_output()
        return 1

    print(
        f"Sent {chunks} message chunk(s) to {platform} target {target_id} for session {current_session}.",
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


def _print_config_error(exc: ConfigError) -> None:
    print(f"tetherly: {exc}", file=sys.stderr)
    print(file=sys.stderr)
    if not USER_ENV_PATH.exists():
        print(
            f"It looks like tetherly isn't set up yet on this machine "
            f"({USER_ENV_PATH} not found).",
            file=sys.stderr,
        )
        print("Run `tetherly init` to walk through interactive setup.", file=sys.stderr)
    else:
        print(f"Config file: {USER_ENV_PATH}", file=sys.stderr)
        print(
            "Inspect with `tetherly config show`, edit with `tetherly config edit`, "
            "or re-run `tetherly init`.",
            file=sys.stderr,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        raise SystemExit(run_init(args))
    if args.command == "install-hooks":
        raise SystemExit(run_install_hooks(args))
    if args.command == "config":
        if args.config_command == "show":
            raise SystemExit(run_config_show())
        if args.config_command == "edit":
            raise SystemExit(run_config_edit())

    load_dotenv()
    try:
        config = Config.from_env()
    except ConfigError as exc:
        _print_config_error(exc)
        raise SystemExit(2)
    config.configure_logging()
    registry = SessionRegistry(config.state_path)
    if args.command in (None, "run-bot"):
        run_bot(config, registry)
        return
    if args.command in ("send", "discord-send"):
        raise SystemExit(run_send(args, config=config, registry=registry))
    if args.command == "codex-stop":
        raise SystemExit(run_codex_stop(config=config, registry=registry))
    if args.command == "codex-permission-request":
        raise SystemExit(run_codex_permission_request(config=config, registry=registry))
