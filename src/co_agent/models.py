from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ChannelBinding:
    guild_id: int
    channel_id: int
    session_name: str
    bound_by: int
    bound_at: str
    last_used_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ChannelBinding":
        return cls(
            guild_id=int(payload["guild_id"]),
            channel_id=int(payload["channel_id"]),
            session_name=str(payload["session_name"]),
            bound_by=int(payload["bound_by"]),
            bound_at=str(payload["bound_at"]),
            last_used_at=str(payload["last_used_at"]),
        )
