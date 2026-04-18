from __future__ import annotations

from co_agent.authz import AccessController
from co_agent.config import Config, load_dotenv
from co_agent.discord_bot import CoAgentBot
from co_agent.session_registry import SessionRegistry
from co_agent.tmux_service import TmuxService


def main() -> None:
    load_dotenv()
    config = Config.from_env()
    config.configure_logging()

    registry = SessionRegistry(config.state_path)
    tmux_service = TmuxService()
    access_controller = AccessController(
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
