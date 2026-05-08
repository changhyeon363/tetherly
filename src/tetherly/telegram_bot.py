from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import Any

from tetherly.config import Config
from tetherly.models import PLATFORM_TELEGRAM
from tetherly.session_registry import SessionRegistry, SessionRegistryError
from tetherly.telegram_sender import (
    TELEGRAM_MESSAGE_LIMIT,
    TelegramSendError,
    answer_callback_query,
    edit_message_text,
    post_message,
    split_message,
)
from tetherly.tmux_service import TmuxError, TmuxService, normalize_session_name


class MessageIntent(str, Enum):
    """Why a notification is being sent. Drives the inline-keyboard layout."""

    PLAIN = "plain"
    STOP = "stop"
    PERMISSION = "permission"


# Inline keyboard layouts ---------------------------------------------------

def _button(label: str, callback_data: str) -> dict[str, str]:
    return {"text": label, "callback_data": callback_data}


def _inline_keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def keyboard_for_intent(intent: MessageIntent) -> dict[str, Any] | None:
    if intent == MessageIntent.STOP:
        return _inline_keyboard(
            [
                [
                    _button("Enter", "key:enter"),
                    _button("Tail", "tail"),
                    _button("Stop", "key:ctrl-c"),
                ]
            ]
        )
    if intent == MessageIntent.PERMISSION:
        return _inline_keyboard(
            [
                [
                    _button("Yes", "key:enter"),
                    _button("No", "key:ctrl-c"),
                    _button("Tail", "tail"),
                ]
            ]
        )
    return None


def keyboard_for_status() -> dict[str, Any]:
    return _inline_keyboard(
        [
            [
                _button("Refresh", "status"),
                _button("Tail", "tail"),
                _button("Enter", "key:enter"),
                _button("Stop", "key:ctrl-c"),
            ]
        ]
    )


def keyboard_for_tail() -> dict[str, Any]:
    return _inline_keyboard(
        [
            [
                _button("Refresh", "tail"),
                _button("Enter", "key:enter"),
                _button("Stop", "key:ctrl-c"),
            ]
        ]
    )

LOGGER = logging.getLogger(__name__)
AUTO_SEND_MAX_LENGTH = 4000

LONG_POLL_TIMEOUT = 25
POLL_RETRY_DELAY = 5

KEY_CHOICES = ("Enter", "Escape", "Ctrl-C", "Ctrl-D", "Tab", "Up", "Down", "Left", "Right")
TRUTHY = {"true", "1", "yes", "on", "enable", "enabled"}
FALSY = {"false", "0", "no", "off", "disable", "disabled"}

COMMAND_DESCRIPTIONS = [
    {"command": "bind", "description": "Bind this chat to a tmux session"},
    {"command": "unbind", "description": "Release this chat from its tmux session"},
    {"command": "config", "description": "auto-send (on|off) or trust_chat <on|off>"},
    {"command": "send", "description": "Send text + Enter to the bound tmux session"},
    {"command": "key", "description": "Send a special key (Enter, Escape, Ctrl-C, ...)"},
    {"command": "tail", "description": "Show recent output from the bound tmux session"},
    {"command": "status", "description": "Show binding and tmux session status"},
    {"command": "enter", "description": "Send Enter (alias for /key Enter)"},
    {"command": "esc", "description": "Send Escape"},
    {"command": "ctrlc", "description": "Send Ctrl-C (interrupt)"},
    {"command": "ctrld", "description": "Send Ctrl-D"},
    {"command": "tab", "description": "Send Tab"},
    {"command": "help", "description": "List available commands"},
]


KEY_ALIAS_COMMANDS = {
    "enter": "enter",
    "esc": "esc",
    "ctrlc": "ctrl-c",
    "ctrld": "ctrl-d",
    "tab": "tab",
}


# Slash commands the bot itself handles. Anything else arriving as
# `/<word>` is forwarded to tmux as auto-send, so users can drive an inner
# CLI (e.g. claude-code's own /help, /clear) directly from chat without
# wrapping every call in `/send …`.
KNOWN_COMMANDS = frozenset(
    {entry["command"] for entry in COMMAND_DESCRIPTIONS} | {"start"}
)


# Prompts shown when a slash command arrives without its required argument.
# We send these with reply_markup={"force_reply": True} so Telegram opens the
# input as a reply — when the user replies, _handle_update detects the reply
# target and dispatches the original command with the reply text as args.
_ARG_PROMPTS = {
    "send": "Reply to this message with the text to send (will be followed by Enter).",
    "bind": "Reply to this message with the tmux session name to bind.",
    "config": (
        "Reply to this message with `on`/`off` (auto-send) "
        "or `trust_chat on`/`trust_chat off`."
    ),
    "key": "Reply to this message with one of: " + ", ".join(KEY_CHOICES) + ".",
}
_PROMPT_TEXT_TO_COMMAND = {text: cmd for cmd, text in _ARG_PROMPTS.items()}


@dataclass(frozen=True)
class TelegramAccessController:
    allowed_user_ids: set[int]
    allowed_chat_ids: set[int]

    def is_allowed(
        self,
        *,
        chat_id: int,
        user_id: int,
        chat_trusted: bool = False,
    ) -> bool:
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return False
        if chat_trusted:
            return True
        if not self.allowed_user_ids:
            return False
        return user_id in self.allowed_user_ids

    def is_privileged(self, user_id: int) -> bool:
        """True only for users on the env-level allowlist.

        Used to gate commands that grant access to others (e.g. flipping
        trust_chat on). chat-membership trust must NOT bootstrap itself.
        """
        return user_id in self.allowed_user_ids


def _render_code_block(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "```\n<empty>\n```"
    truncated = stripped[:1800]
    return f"```\n{truncated}\n```"


def _parse_bool(token: str) -> bool | None:
    if token in TRUTHY:
        return True
    if token in FALSY:
        return False
    return None


def _match_arg_prompt_reply(message: dict) -> str | None:
    """If `message` is a reply to one of our ForceReply prompts, return the command."""
    reply_to = message.get("reply_to_message")
    if not isinstance(reply_to, dict):
        return None
    sender = reply_to.get("from") or {}
    if not sender.get("is_bot"):
        return None
    text = reply_to.get("text") or ""
    return _PROMPT_TEXT_TO_COMMAND.get(text)


def _parse_command(text: str) -> tuple[str, str] | None:
    """Return (command, args_text) or None when this isn't a slash command."""
    if not text or not text.startswith("/"):
        return None
    head, _, rest = text.partition(" ")
    command = head[1:]
    if "@" in command:
        command = command.split("@", 1)[0]
    if not command:
        return None
    return command.lower(), rest.strip()


class TelegramBot:
    def __init__(
        self,
        *,
        config: Config,
        registry: SessionRegistry,
        tmux_service: TmuxService,
        access_controller: TelegramAccessController,
    ) -> None:
        if not config.telegram_bot_token:
            raise ValueError("telegram_bot_token must be configured")
        self.config = config
        self.registry = registry
        self.tmux_service = tmux_service
        self.access_controller = access_controller
        self._token = config.telegram_bot_token
        self._offset: int | None = None

    async def run(self) -> None:
        import aiohttp

        async with aiohttp.ClientSession() as session:
            LOGGER.info("telegram bot started")
            await self._register_commands(session)
            while True:
                try:
                    updates = await self._poll(session)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 — keep polling alive
                    LOGGER.warning("telegram poll error: %s", exc)
                    await asyncio.sleep(POLL_RETRY_DELAY)
                    continue
                for update in updates:
                    try:
                        await self._handle_update(session, update)
                    except Exception:  # noqa: BLE001 — never crash the loop
                        LOGGER.exception("error handling telegram update")

    async def _register_commands(self, session) -> None:
        url = f"https://api.telegram.org/bot{self._token}/setMyCommands"
        body = {"commands": COMMAND_DESCRIPTIONS}
        try:
            async with session.post(url, json=body, timeout=10) as response:
                if response.status >= 400:
                    text = await response.text()
                    LOGGER.warning("setMyCommands failed (%s): %s", response.status, text)
        except Exception as exc:  # noqa: BLE001 — never block startup on this
            LOGGER.warning("setMyCommands errored: %s", exc)

    async def _poll(self, session) -> list[dict]:
        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        params: dict[str, object] = {
            "timeout": LONG_POLL_TIMEOUT,
            "allowed_updates": '["message","callback_query"]',
        }
        if self._offset is not None:
            params["offset"] = self._offset
        timeout = LONG_POLL_TIMEOUT + 10
        async with session.get(url, params=params, timeout=timeout) as response:
            if response.status >= 400:
                body = await response.text()
                raise RuntimeError(f"getUpdates failed {response.status}: {body}")
            payload = await response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"getUpdates not ok: {payload!r}")
        updates = payload.get("result") or []
        if updates:
            self._offset = max(int(u["update_id"]) for u in updates) + 1
        return updates

    async def _handle_update(self, session, update: dict) -> None:
        if isinstance(update.get("callback_query"), dict):
            await self._handle_callback_query(session, update["callback_query"])
            return

        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        chat_id = chat.get("id")
        user_id = sender.get("id")
        text = message.get("text")
        if not isinstance(chat_id, int) or not isinstance(user_id, int):
            return
        if not isinstance(text, str) or not text:
            return

        prompt_command = _match_arg_prompt_reply(message)
        parsed = _parse_command(text)

        if prompt_command is not None:
            command = prompt_command
            args = text.strip()
        elif parsed is None:
            await self._maybe_auto_send(session, chat_id, user_id, text)
            return
        else:
            command, args = parsed
            if command not in KNOWN_COMMANDS:
                # Not one of our commands — let the inner CLI see it.
                await self._maybe_auto_send(session, chat_id, user_id, text)
                return

        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        chat_trusted = binding is not None and binding.trust_chat
        if not self.access_controller.is_allowed(
            chat_id=chat_id, user_id=user_id, chat_trusted=chat_trusted
        ):
            LOGGER.info(
                "telegram: ignored /%s from chat=%s user=%s (not on allowlist)",
                command,
                chat_id,
                user_id,
            )
            return

        message_id = message.get("message_id") if isinstance(message.get("message_id"), int) else None
        try:
            await self._dispatch(
                session, chat_id, user_id, command, args, source_message_id=message_id
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("command %s failed", command)
            await self._reply(session, chat_id, "Internal error. Check the bot logs.")

    async def _handle_callback_query(self, session, callback: dict) -> None:
        callback_id = callback.get("id")
        if not isinstance(callback_id, str):
            return
        sender = callback.get("from") or {}
        user_id = sender.get("id")
        message = callback.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        data = callback.get("data")
        if (
            not isinstance(user_id, int)
            or not isinstance(chat_id, int)
            or not isinstance(message_id, int)
            or not isinstance(data, str)
        ):
            await self._answer_callback(callback_id)
            return

        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        chat_trusted = binding is not None and binding.trust_chat
        if not self.access_controller.is_allowed(
            chat_id=chat_id, user_id=user_id, chat_trusted=chat_trusted
        ):
            LOGGER.info(
                "telegram: ignored callback %r from chat=%s user=%s (not on allowlist)",
                data,
                chat_id,
                user_id,
            )
            await self._answer_callback(callback_id)
            return

        try:
            await self._dispatch_callback(
                session, chat_id, message_id, data, callback_id
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("callback %s failed", data)
            await self._answer_callback(callback_id, text="Error")

    async def _dispatch_callback(
        self,
        session,
        chat_id: int,
        message_id: int,
        data: str,
        callback_id: str,
    ) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._answer_callback(callback_id, text="Not bound")
            return

        if data.startswith("key:"):
            key = data.split(":", 1)[1]
            try:
                self.tmux_service.send_key(binding.session_name, key)
            except TmuxError as exc:
                await self._answer_callback(callback_id, text=f"Failed: {exc}")
                return
            self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)
            await self._answer_callback(callback_id, text=f"Sent {key}")
            return

        if data == "tail":
            requested = self.config.default_tail_lines
            capped = min(max(1, requested), self.config.max_tail_lines)
            try:
                output = self.tmux_service.capture_tail(binding.session_name, capped)
            except TmuxError as exc:
                await self._answer_callback(callback_id, text=f"Failed: {exc}")
                return
            self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)
            body = (
                f"Recent output from `{binding.session_name}` ({capped} lines max)\n"
                f"{_render_code_block(output)}"
            )
            await self._edit(session, chat_id, message_id, body, keyboard_for_tail())
            await self._answer_callback(callback_id)
            return

        if data == "status":
            tmux_status = self.tmux_service.get_status(binding.session_name)
            if tmux_status.exists:
                headline = f"🟢 Active — tmux session `{binding.session_name}` is alive"
            else:
                headline = (
                    f"🔴 tmux session `{binding.session_name}` is GONE — "
                    "run `/bind <session>` to reconnect"
                )
            body = "\n".join(
                [
                    headline,
                    f"Chat ID: `{binding.channel_id}`",
                    f"Auto-send: `{binding.auto_send}`",
                    f"Bound by: `{binding.bound_by}`",
                    f"Bound at: `{binding.bound_at}`",
                    f"Last used at: `{binding.last_used_at}`",
                ]
            )
            await self._edit(session, chat_id, message_id, body, keyboard_for_status())
            await self._answer_callback(callback_id)
            return

        await self._answer_callback(callback_id, text="Unknown action")

    async def _answer_callback(
        self, callback_id: str, *, text: str | None = None
    ) -> None:
        try:
            await answer_callback_query(self._token, callback_id, text=text)
        except TelegramSendError as exc:
            LOGGER.warning("answerCallbackQuery failed: %s", exc)

    async def _edit(
        self,
        session,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None,
    ) -> None:
        del session  # sender opens its own
        try:
            await edit_message_text(
                self._token,
                chat_id,
                message_id,
                text[:TELEGRAM_MESSAGE_LIMIT],
                reply_markup=reply_markup,
            )
        except TelegramSendError as exc:
            LOGGER.warning("editMessageText failed: %s", exc)

    async def _maybe_auto_send(
        self, session, chat_id: int, user_id: int, text: str
    ) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None or not binding.auto_send:
            return
        if not self.access_controller.is_allowed(
            chat_id=chat_id, user_id=user_id, chat_trusted=binding.trust_chat
        ):
            return
        content = text.strip()
        if not content or len(content) > AUTO_SEND_MAX_LENGTH:
            return
        try:
            self.tmux_service.send_text(binding.session_name, content, press_enter=True)
        except TmuxError as exc:
            LOGGER.warning(
                "telegram auto-send failed for chat %s session %s: %s",
                chat_id,
                binding.session_name,
                exc,
            )
            return
        self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)

    async def _dispatch(
        self,
        session,
        chat_id: int,
        user_id: int,
        command: str,
        args: str,
        *,
        source_message_id: int | None = None,
    ) -> None:
        if command == "bind":
            await self._cmd_bind(
                session, chat_id, user_id, args, source_message_id=source_message_id
            )
        elif command == "unbind":
            await self._cmd_unbind(session, chat_id, user_id, args)
        elif command == "config":
            await self._cmd_config(
                session, chat_id, user_id, args, source_message_id=source_message_id
            )
        elif command == "send":
            await self._cmd_send(
                session, chat_id, args, source_message_id=source_message_id
            )
        elif command == "key":
            await self._cmd_key(
                session, chat_id, args, source_message_id=source_message_id
            )
        elif command == "tail":
            await self._cmd_tail(session, chat_id, args)
        elif command == "status":
            await self._cmd_status(session, chat_id)
        elif command in KEY_ALIAS_COMMANDS:
            await self._cmd_key_alias(session, chat_id, KEY_ALIAS_COMMANDS[command])
        elif command in ("start", "help"):
            await self._reply(session, chat_id, _help_text())
        # silently ignore unknown commands so the bot doesn't spam other groups

    async def _cmd_key_alias(self, session, chat_id: int, key: str) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(
                session,
                chat_id,
                "This chat is not bound. Run `/bind <session>` first.",
            )
            return
        try:
            self.tmux_service.send_key(binding.session_name, key)
        except TmuxError as exc:
            await self._reply(
                session,
                chat_id,
                f"Failed to send `{key}` to `{binding.session_name}`: {exc}",
            )
            return
        self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)
        await self._reply(session, chat_id, f"Sent `{key}` to `{binding.session_name}`.")

    async def _cmd_bind(
        self,
        session,
        chat_id: int,
        user_id: int,
        args: str,
        *,
        source_message_id: int | None = None,
    ) -> None:
        if not self.access_controller.is_privileged(user_id):
            await self._reply(
                session, chat_id, "Only the bot owner can /bind."
            )
            return
        session_arg = args.strip()
        if not session_arg:
            await self._prompt_for_arg(session, chat_id, "bind", source_message_id)
            return
        try:
            session_name = normalize_session_name(session_arg)
        except ValueError as exc:
            await self._reply(session, chat_id, str(exc))
            return
        try:
            created = self.tmux_service.ensure_session(session_name)
            self.tmux_service.set_session_environment(
                session_name, "TETHERLY_SESSION", session_name
            )
            self.tmux_service.set_session_environment(
                session_name, "TETHERLY_NOTIFY_ON_FINISH", "1"
            )
        except TmuxError as exc:
            await self._reply(session, chat_id, f"tmux error: {exc}")
            return
        try:
            binding = self.registry.bind(
                guild_id=chat_id,
                channel_id=chat_id,
                session_name=session_name,
                bound_by=user_id,
                platform=PLATFORM_TELEGRAM,
            )
        except SessionRegistryError as exc:
            await self._reply(session, chat_id, str(exc))
            return
        verb = "Created and bound" if created else "Bound"
        await self._reply(
            session,
            chat_id,
            f"{verb} this chat to tmux session `{binding.session_name}`.",
        )

    async def _cmd_unbind(
        self, session, chat_id: int, user_id: int, args: str
    ) -> None:
        if not self.access_controller.is_privileged(user_id):
            await self._reply(
                session, chat_id, "Only the bot owner can /unbind."
            )
            return
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(session, chat_id, "This chat is not bound.")
            return
        try:
            self.tmux_service.set_session_environment(
                binding.session_name, "TETHERLY_NOTIFY_ON_FINISH", ""
            )
        except TmuxError:
            pass
        self.registry.unbind(chat_id, platform=PLATFORM_TELEGRAM)
        await self._reply(
            session,
            chat_id,
            f"Unbound this chat from tmux session `{binding.session_name}`.",
        )

    async def _cmd_config(
        self,
        session,
        chat_id: int,
        user_id: int,
        args: str,
        *,
        source_message_id: int | None = None,
    ) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(
                session,
                chat_id,
                "This chat is not bound. Run `/bind <session>` first.",
            )
            return
        raw = args.strip()
        if not raw:
            await self._prompt_for_arg(session, chat_id, "config", source_message_id)
            return
        tokens = raw.lower().split()
        # `/config trust_chat <on|off>` vs the legacy `/config <on|off>` shortcut for auto_send.
        if tokens[0] == "trust_chat":
            if len(tokens) != 2:
                await self._reply(
                    session, chat_id, "Usage: /config trust_chat <on|off>"
                )
                return
            enabled = _parse_bool(tokens[1])
            if enabled is None:
                await self._reply(session, chat_id, "Expected `on` or `off`.")
                return
            if not self.access_controller.is_privileged(user_id):
                LOGGER.info(
                    "telegram: refused trust_chat flip from chat=%s user=%s (not privileged)",
                    chat_id,
                    user_id,
                )
                return
            updated = self.registry.set_trust_chat(
                chat_id, enabled, platform=PLATFORM_TELEGRAM
            )
            if enabled:
                await self._reply(
                    session,
                    chat_id,
                    f"Trust-chat **enabled** for `{updated.session_name}`. "
                    "Every member of this chat can now run commands.",
                )
            else:
                await self._reply(
                    session,
                    chat_id,
                    f"Trust-chat disabled for `{updated.session_name}`. "
                    "Only allowlisted users can run commands again.",
                )
            return

        if len(tokens) == 1:
            enabled = _parse_bool(tokens[0])
        elif len(tokens) == 2 and tokens[0] == "auto_send":
            enabled = _parse_bool(tokens[1])
        else:
            enabled = None
        if enabled is None:
            await self._reply(
                session,
                chat_id,
                "Expected `on`, `off`, or `trust_chat on|off`.",
            )
            return
        updated = self.registry.set_auto_send(
            chat_id, enabled, platform=PLATFORM_TELEGRAM
        )
        status = "enabled" if enabled else "disabled"
        await self._reply(
            session,
            chat_id,
            f"Auto-send {status} for `{updated.session_name}`.",
        )

    async def _cmd_send(
        self,
        session,
        chat_id: int,
        args: str,
        *,
        source_message_id: int | None = None,
    ) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(
                session,
                chat_id,
                "This chat is not bound. Run `/bind <session>` first.",
            )
            return
        text = args
        if not text.strip():
            await self._prompt_for_arg(session, chat_id, "send", source_message_id)
            return
        try:
            self.tmux_service.send_text(binding.session_name, text, press_enter=True)
        except TmuxError as exc:
            await self._reply(
                session,
                chat_id,
                f"Failed to send to `{binding.session_name}`: {exc}",
            )
            return
        self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)
        await self._reply(session, chat_id, f"Sent to `{binding.session_name}`.")

    async def _cmd_key(
        self,
        session,
        chat_id: int,
        args: str,
        *,
        source_message_id: int | None = None,
    ) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(
                session,
                chat_id,
                "This chat is not bound. Run `/bind <session>` first.",
            )
            return
        raw = args.strip()
        if not raw:
            await self._prompt_for_arg(session, chat_id, "key", source_message_id)
            return
        try:
            self.tmux_service.send_key(binding.session_name, raw)
        except TmuxError as exc:
            await self._reply(
                session,
                chat_id,
                f"Failed to send `{raw}` to `{binding.session_name}`: {exc}",
            )
            return
        self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)
        await self._reply(session, chat_id, f"Sent `{raw}` to `{binding.session_name}`.")

    async def _cmd_tail(self, session, chat_id: int, args: str) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(
                session,
                chat_id,
                "This chat is not bound. Run `/bind <session>` first.",
            )
            return
        requested = self.config.default_tail_lines
        raw = args.strip()
        if raw:
            try:
                requested = int(shlex.split(raw)[0])
            except (ValueError, IndexError):
                await self._reply(session, chat_id, "Usage: /tail [lines]")
                return
        capped = min(max(1, requested), self.config.max_tail_lines)
        try:
            output = self.tmux_service.capture_tail(binding.session_name, capped)
        except TmuxError as exc:
            await self._reply(
                session,
                chat_id,
                f"Failed to capture `{binding.session_name}`: {exc}",
            )
            return
        self.registry.touch(chat_id, platform=PLATFORM_TELEGRAM)
        body = (
            f"Recent output from `{binding.session_name}` ({capped} lines max)\n"
            f"{_render_code_block(output)}"
        )
        await self._reply(session, chat_id, body, reply_markup=keyboard_for_tail())

    async def _cmd_status(self, session, chat_id: int) -> None:
        binding = self.registry.get(chat_id, platform=PLATFORM_TELEGRAM)
        if binding is None:
            await self._reply(session, chat_id, "This chat is not bound.")
            return
        tmux_status = self.tmux_service.get_status(binding.session_name)
        if tmux_status.exists:
            headline = f"🟢 Active — tmux session `{binding.session_name}` is alive"
        else:
            headline = (
                f"🔴 tmux session `{binding.session_name}` is GONE — "
                "run `/bind <session>` to reconnect"
            )
        body = "\n".join(
            [
                headline,
                f"Chat ID: `{binding.channel_id}`",
                f"Auto-send: `{binding.auto_send}`",
                f"Trust chat: `{binding.trust_chat}`",
                f"Bound by: `{binding.bound_by}`",
                f"Bound at: `{binding.bound_at}`",
                f"Last used at: `{binding.last_used_at}`",
            ]
        )
        await self._reply(session, chat_id, body, reply_markup=keyboard_for_status())

    async def _reply(
        self,
        session,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        del session  # unused — sender opens its own session for now
        chunks = split_message(text, limit=TELEGRAM_MESSAGE_LIMIT)
        for index, chunk in enumerate(chunks):
            markup = reply_markup if index == len(chunks) - 1 else None
            try:
                await post_message(self._token, chat_id, chunk, reply_markup=markup)
            except TelegramSendError as exc:
                LOGGER.warning("telegram reply failed: %s", exc)
                return

    async def _prompt_for_arg(
        self,
        session,
        chat_id: int,
        command: str,
        source_message_id: int | None = None,
    ) -> None:
        """Send a ForceReply prompt; user's reply is captured by _handle_update.

        The prompt is sent as a reply to the user's slash-command message so
        the conversational thread stays clear, and `selective` is omitted so
        Telegram opens the reply UI immediately in DMs.
        """
        prompt = _ARG_PROMPTS[command]
        del session  # _reply manages its own session
        try:
            await post_message(
                self._token,
                chat_id,
                prompt,
                reply_markup={"force_reply": True},
                reply_to_message_id=source_message_id,
            )
        except TelegramSendError as exc:
            LOGGER.warning("force-reply prompt failed: %s", exc)


def _help_text() -> str:
    lines = [
        "tetherly — Telegram ↔ tmux bridge",
        "",
        "Commands:",
        "  /bind <session>      — bind this chat to a tmux session",
        "  /unbind              — release this chat",
        "  /config <on|off>     — toggle plain-text auto-send",
        "  /config trust_chat <on|off> — let everyone in this chat run commands",
        "  /send <text>         — send text + Enter to tmux",
        "  /key <" + "|".join(KEY_CHOICES) + "> — send a special key",
        "  /tail [lines]        — show recent tmux output",
        "  /status              — show binding state",
        "",
        "Quick keys (no args):",
        "  /enter /esc /ctrlc /ctrld /tab",
        "",
        "Tip: alerts include inline buttons — just tap them.",
    ]
    return "\n".join(lines)
