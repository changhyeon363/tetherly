from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from tetherly.models import PLATFORM_DISCORD, ChannelBinding, utc_now


class SessionRegistryError(RuntimeError):
    pass


BindingKey = tuple[str, int]


class SessionRegistry:
    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path
        self._bindings: dict[BindingKey, ChannelBinding] = {}
        self._load()

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text())
        bindings = payload.get("bindings", [])
        loaded: dict[BindingKey, ChannelBinding] = {}
        for item in bindings:
            binding = ChannelBinding.from_dict(item)
            loaded[(binding.platform, binding.channel_id)] = binding
        self._bindings = loaded

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "bindings": [binding.to_dict() for binding in self._bindings.values()],
        }
        self._state_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def get(
        self, channel_id: int, *, platform: str = PLATFORM_DISCORD
    ) -> ChannelBinding | None:
        return self._bindings.get((platform, channel_id))

    def get_by_session_name(self, session_name: str) -> ChannelBinding | None:
        """Return the (globally unique) binding for a session, regardless of platform."""
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
        platform: str = PLATFORM_DISCORD,
    ) -> ChannelBinding:
        existing = self.get_by_session_name(session_name)
        if existing is not None and (
            existing.platform != platform or existing.channel_id != channel_id
        ):
            raise SessionRegistryError(
                f"session {session_name!r} is already bound to "
                f"{existing.platform} channel {existing.channel_id}; "
                "run /unbind there first"
            )
        now = utc_now()
        binding = ChannelBinding(
            guild_id=guild_id,
            channel_id=channel_id,
            session_name=session_name,
            auto_send=False,
            bound_by=bound_by,
            bound_at=now,
            last_used_at=now,
            platform=platform,
            trust_chat=False,
        )
        self._bindings[(platform, channel_id)] = binding
        self._save()
        return binding

    def unbind(
        self, channel_id: int, *, platform: str = PLATFORM_DISCORD
    ) -> ChannelBinding | None:
        key = (platform, channel_id)
        binding = self._bindings.pop(key, None)
        if binding is not None:
            self._save()
        return binding

    def set_auto_send(
        self,
        channel_id: int,
        enabled: bool,
        *,
        platform: str = PLATFORM_DISCORD,
    ) -> ChannelBinding | None:
        key = (platform, channel_id)
        binding = self._bindings.get(key)
        if binding is None:
            return None
        updated = replace(
            binding,
            auto_send=enabled,
            last_used_at=utc_now(),
        )
        self._bindings[key] = updated
        self._save()
        return updated

    def set_trust_chat(
        self,
        channel_id: int,
        enabled: bool,
        *,
        platform: str = PLATFORM_DISCORD,
    ) -> ChannelBinding | None:
        key = (platform, channel_id)
        binding = self._bindings.get(key)
        if binding is None:
            return None
        updated = replace(
            binding,
            trust_chat=enabled,
            last_used_at=utc_now(),
        )
        self._bindings[key] = updated
        self._save()
        return updated

    def touch(
        self, channel_id: int, *, platform: str = PLATFORM_DISCORD
    ) -> ChannelBinding | None:
        key = (platform, channel_id)
        binding = self._bindings.get(key)
        if binding is None:
            return None
        updated = replace(binding, last_used_at=utc_now())
        self._bindings[key] = updated
        self._save()
        return updated
