from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    dotenv_path = Path(path)
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _parse_id_set(raw: str | None) -> set[int]:
    if not raw:
        return set()
    values: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.add(int(chunk))
    return values


@dataclass(frozen=True)
class Config:
    discord_bot_token: str
    state_path: Path
    allowed_guild_ids: set[int]
    allowed_role_ids: set[int]
    allowed_user_ids: set[int]
    test_guild_id: int | None = None
    default_tail_lines: int = 40
    max_tail_lines: int = 200
    log_level: str = "INFO"
    command_prefix: str = "/"

    @classmethod
    def from_env(cls) -> "Config":
        token = os.environ["DISCORD_BOT_TOKEN"].strip()
        state_path = Path(os.environ.get("CO_AGENT_STATE_PATH", ".co-agent/state.json"))
        return cls(
            discord_bot_token=token,
            state_path=state_path,
            allowed_guild_ids=_parse_id_set(os.environ.get("CO_AGENT_ALLOWED_GUILD_IDS")),
            allowed_role_ids=_parse_id_set(os.environ.get("CO_AGENT_ALLOWED_ROLE_IDS")),
            allowed_user_ids=_parse_id_set(os.environ.get("CO_AGENT_ALLOWED_USER_IDS")),
            test_guild_id=int(os.environ["CO_AGENT_TEST_GUILD_ID"])
            if os.environ.get("CO_AGENT_TEST_GUILD_ID")
            else None,
            default_tail_lines=int(os.environ.get("CO_AGENT_DEFAULT_TAIL_LINES", "40")),
            max_tail_lines=int(os.environ.get("CO_AGENT_MAX_TAIL_LINES", "200")),
            log_level=os.environ.get("CO_AGENT_LOG_LEVEL", "INFO").upper(),
        )

    def configure_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
