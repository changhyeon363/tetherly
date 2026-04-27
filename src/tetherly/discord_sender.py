from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tetherly.config import Config
from tetherly.session_registry import SessionRegistry

DISCORD_MESSAGE_LIMIT = 2000


class DiscordSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class SendResult:
    channel_id: int
    session_name: str
    chunks_sent: int


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    normalized = text.strip()
    if not normalized:
        raise DiscordSendError("message is empty")
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


async def _post_message(token: str, channel_id: int, content: str) -> None:
    import aiohttp

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, json={"content": content}) as response:
            if response.status >= 400:
                body = await response.text()
                raise DiscordSendError(
                    f"discord send failed with status {response.status}: {body}"
                )


async def send_to_session_async(
    *,
    config: Config,
    registry: SessionRegistry,
    session_name: str,
    message: str,
) -> SendResult:
    binding = registry.get_by_session_name(session_name)
    if binding is None:
        raise DiscordSendError(f"no bound Discord channel for session {session_name!r}")
    chunks = split_message(message)
    for chunk in chunks:
        await _post_message(config.discord_bot_token, binding.channel_id, chunk)
    registry.touch(binding.channel_id)
    return SendResult(
        channel_id=binding.channel_id,
        session_name=session_name,
        chunks_sent=len(chunks),
    )


def send_to_session(
    *,
    config: Config,
    registry: SessionRegistry,
    session_name: str,
    message: str,
) -> SendResult:
    return asyncio.run(
        send_to_session_async(
            config=config,
            registry=registry,
            session_name=session_name,
            message=message,
        )
    )
