from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


USER_CONFIG_DIR = Path.home() / ".tetherly"
USER_ENV_PATH = USER_CONFIG_DIR / ".env"
USER_STATE_PATH = USER_CONFIG_DIR / "state.json"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
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


def load_dotenv(path: str = ".env") -> None:
    _load_env_file(Path(path))
    _load_env_file(USER_ENV_PATH)


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


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    discord_bot_token: str | None
    telegram_bot_token: str | None
    state_path: Path
    allowed_guild_ids: set[int]
    allowed_role_ids: set[int]
    allowed_user_ids: set[int]
    telegram_allowed_user_ids: set[int]
    telegram_allowed_chat_ids: set[int]
    test_guild_id: int | None = None
    default_tail_lines: int = 40
    max_tail_lines: int = 200
    log_level: str = "INFO"
    command_prefix: str = "/"

    @classmethod
    def from_env(cls) -> "Config":
        discord_token = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip() or None
        telegram_token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip() or None
        if not discord_token and not telegram_token:
            raise ConfigError(
                "At least one of DISCORD_BOT_TOKEN or TELEGRAM_BOT_TOKEN must be set."
            )
        state_path = Path(os.environ.get("TETHERLY_STATE_PATH", str(USER_STATE_PATH)))
        return cls(
            discord_bot_token=discord_token,
            telegram_bot_token=telegram_token,
            state_path=state_path,
            allowed_guild_ids=_parse_id_set(os.environ.get("TETHERLY_ALLOWED_GUILD_IDS")),
            allowed_role_ids=_parse_id_set(os.environ.get("TETHERLY_ALLOWED_ROLE_IDS")),
            allowed_user_ids=_parse_id_set(os.environ.get("TETHERLY_ALLOWED_USER_IDS")),
            telegram_allowed_user_ids=_parse_id_set(
                os.environ.get("TETHERLY_TELEGRAM_ALLOWED_USER_IDS")
            ),
            telegram_allowed_chat_ids=_parse_id_set(
                os.environ.get("TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS")
            ),
            test_guild_id=int(os.environ["TETHERLY_TEST_GUILD_ID"])
            if os.environ.get("TETHERLY_TEST_GUILD_ID")
            else None,
            default_tail_lines=int(os.environ.get("TETHERLY_DEFAULT_TAIL_LINES", "40")),
            max_tail_lines=int(os.environ.get("TETHERLY_MAX_TAIL_LINES", "200")),
            log_level=os.environ.get("TETHERLY_LOG_LEVEL", "INFO").upper(),
        )

    def configure_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
