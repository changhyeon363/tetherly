from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from co_agent.models import ChannelBinding, utc_now


class SessionRegistryError(RuntimeError):
    pass


class SessionRegistry:
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path
        self._bindings: dict[int, ChannelBinding] = {}
        self._load()

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text())
        bindings = payload.get("bindings", [])
        self._bindings = {
            int(item["channel_id"]): ChannelBinding.from_dict(item)
            for item in bindings
        }

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "bindings": [binding.to_dict() for binding in self._bindings.values()],
        }
        self._state_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def get(self, channel_id: int) -> ChannelBinding | None:
        return self._bindings.get(channel_id)

    def get_by_session_name(self, session_name: str) -> ChannelBinding | None:
        for binding in self._bindings.values():
            if binding.session_name == session_name:
                return binding
        return None

    def bind(
        self,
        *,
        guild_id: int,
        channel_id: int,
        session_name: str,
        bound_by: int,
    ) -> ChannelBinding:
        existing = self.get_by_session_name(session_name)
        if existing is not None and existing.channel_id != channel_id:
            raise SessionRegistryError(
                f"session {session_name!r} is already bound to channel {existing.channel_id}"
            )
        now = utc_now()
        binding = ChannelBinding(
            guild_id=guild_id,
            channel_id=channel_id,
            session_name=session_name,
            bound_by=bound_by,
            bound_at=now,
            last_used_at=now,
        )
        self._bindings[channel_id] = binding
        self._save()
        return binding

    def touch(self, channel_id: int) -> ChannelBinding | None:
        binding = self._bindings.get(channel_id)
        if binding is None:
            return None
        updated = replace(binding, last_used_at=utc_now())
        self._bindings[channel_id] = updated
        self._save()
        return updated
