from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from tetherly.config import Config
from tetherly.models import PLATFORM_TELEGRAM
from tetherly.session_registry import SessionRegistry

TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class TelegramSendResult:
    chat_id: int
    session_name: str
    chunks_sent: int


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    normalized = text.strip()
    if not normalized:
        raise TelegramSendError("message is empty")
    chunks: list[str] = []
    remaining = normalized
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip("\n")
    return chunks


async def post_message(
    token: str,
    chat_id: int,
    content: str,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    import aiohttp

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": content}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status >= 400:
                body = await response.text()
                raise TelegramSendError(
                    f"telegram send failed with status {response.status}: {body}"
                )


async def edit_message_text(
    token: str,
    chat_id: int,
    message_id: int,
    content: str,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> None:
    import aiohttp

    url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": content,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status >= 400:
                body = await response.text()
                raise TelegramSendError(
                    f"telegram edit failed with status {response.status}: {body}"
                )


async def answer_callback_query(
    token: str,
    callback_query_id: str,
    *,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    import aiohttp

    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text is not None:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status >= 400:
                body = await response.text()
                raise TelegramSendError(
                    f"answerCallbackQuery failed with status {response.status}: {body}"
                )


async def send_to_session_async(
    *,
    config: Config,
    registry: SessionRegistry,
    session_name: str,
    message: str,
    reply_markup: dict[str, Any] | None = None,
) -> TelegramSendResult:
    if not config.telegram_bot_token:
        raise TelegramSendError("TELEGRAM_BOT_TOKEN is not configured")
    binding = registry.get_by_session_name(session_name)
    if binding is None or binding.platform != PLATFORM_TELEGRAM:
        raise TelegramSendError(
            f"no bound Telegram chat for session {session_name!r}"
        )
    chunks = split_message(message)
    for index, chunk in enumerate(chunks):
        # Only attach the keyboard to the last chunk so it lives on the visible message.
        markup = reply_markup if index == len(chunks) - 1 else None
        await post_message(
            config.telegram_bot_token,
            binding.channel_id,
            chunk,
            reply_markup=markup,
        )
    registry.touch(binding.channel_id, platform=PLATFORM_TELEGRAM)
    return TelegramSendResult(
        chat_id=binding.channel_id,
        session_name=session_name,
        chunks_sent=len(chunks),
    )


def send_to_session(
    *,
    config: Config,
    registry: SessionRegistry,
    session_name: str,
    message: str,
    reply_markup: dict[str, Any] | None = None,
) -> TelegramSendResult:
    return asyncio.run(
        send_to_session_async(
            config=config,
            registry=registry,
            session_name=session_name,
            message=message,
            reply_markup=reply_markup,
        )
    )
