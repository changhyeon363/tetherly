from __future__ import annotations

import logging

import discord
from discord import app_commands

from co_agent.authz import AccessController
from co_agent.config import Config
from co_agent.session_registry import SessionRegistry, SessionRegistryError
from co_agent.tmux_service import TmuxError, TmuxService, normalize_session_name

LOGGER = logging.getLogger(__name__)
AUTO_SEND_MAX_LENGTH = 4000


def _render_code_block(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "```text\n<empty>\n```"
    return f"```text\n{stripped[:1800]}\n```"


def _extract_auto_send_text(message: discord.Message) -> str | None:
    if message.author.bot or message.webhook_id is not None:
        return None
    if message.guild is None or isinstance(message.channel, discord.Thread):
        return None
    if message.type is not discord.MessageType.default:
        return None
    if message.reference is not None or message.attachments:
        return None
    content = message.content.strip()
    if not content or content.startswith("/") or len(content) > AUTO_SEND_MAX_LENGTH:
        return None
    return content


class CoAgentBot(discord.Client):
    def __init__(
        self,
        *,
        config: Config,
        registry: SessionRegistry,
        tmux_service: TmuxService,
        access_controller: AccessController,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.registry = registry
        self.tmux_service = tmux_service
        self.access_controller = access_controller
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self._register_commands()
        if self.config.test_guild_id is not None:
            guild = discord.Object(id=self.config.test_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            LOGGER.info("synced commands to guild %s", self.config.test_guild_id)
            return
        await self.tree.sync()

    async def on_ready(self) -> None:
        LOGGER.info("bot ready as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        binding = self.registry.get(message.channel.id)
        if binding is None or not binding.auto_send:
            return
        if not self.access_controller.is_allowed_user(message.guild.id, message.author):
            return
        content = _extract_auto_send_text(message)
        if content is None:
            return
        try:
            self.tmux_service.send_text(binding.session_name, content, press_enter=True)
        except TmuxError as exc:
            LOGGER.warning(
                "auto-send failed for channel %s session %s: %s",
                binding.channel_id,
                binding.session_name,
                exc,
            )
            return
        self.registry.touch(binding.channel_id)

    def _register_commands(self) -> None:
        @self.tree.command(name="bind", description="Bind this Discord channel to a tmux session.")
        @app_commands.describe(session="tmux session name")
        async def bind(interaction: discord.Interaction, session: str) -> None:
            if not await self.access_controller.assert_allowed(interaction):
                return
            if interaction.guild_id is None or interaction.channel_id is None:
                await interaction.response.send_message(
                    "This command can only be used inside a guild channel.",
                    ephemeral=True,
                )
                return
            try:
                session_name = normalize_session_name(session)
            except ValueError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            created = self.tmux_service.ensure_session(session_name)
            self.tmux_service.set_session_environment(
                session_name,
                "CO_AGENT_SESSION",
                session_name,
            )
            self.tmux_service.set_session_environment(
                session_name,
                "CO_AGENT_NOTIFY_ON_FINISH",
                "1",
            )
            try:
                binding = self.registry.bind(
                    guild_id=interaction.guild_id,
                    channel_id=interaction.channel_id,
                    session_name=session_name,
                    bound_by=interaction.user.id,
                )
            except SessionRegistryError as exc:
                await interaction.response.send_message(str(exc), ephemeral=True)
                return
            verb = "Created and bound" if created else "Bound"
            await interaction.response.send_message(
                f"{verb} channel <#{binding.channel_id}> to tmux session `{binding.session_name}`.",
                ephemeral=True,
            )

        @self.tree.command(
            name="config",
            description="Configure channel behavior for the bound tmux session.",
        )
        @app_commands.describe(auto_send="forward plain text messages without using /send")
        async def config(interaction: discord.Interaction, auto_send: bool) -> None:
            if not await self.access_controller.assert_allowed(interaction):
                return
            binding = self.registry.get(interaction.channel_id)
            if binding is None:
                await interaction.response.send_message(
                    "This channel is not bound. Run `/bind session:<name>` first.",
                    ephemeral=True,
                )
                return
            updated = self.registry.set_auto_send(interaction.channel_id, auto_send)
            status = "enabled" if auto_send else "disabled"
            await interaction.response.send_message(
                f"Auto-send {status} for `{updated.session_name}`.",
                ephemeral=True,
            )

        @self.tree.command(name="send", description="Send text into the bound tmux session and press Enter.")
        @app_commands.describe(text="text to send")
        async def send(interaction: discord.Interaction, text: str) -> None:
            if not await self.access_controller.assert_allowed(interaction):
                return
            binding = self.registry.get(interaction.channel_id)
            if binding is None:
                await interaction.response.send_message(
                    "This channel is not bound. Run `/bind session:<name>` first.",
                    ephemeral=True,
                )
                return
            try:
                self.tmux_service.send_text(binding.session_name, text, press_enter=True)
            except TmuxError as exc:
                await interaction.response.send_message(
                    f"Failed to send to `{binding.session_name}`: {exc}",
                    ephemeral=True,
                )
                return
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                f"Sent to `{binding.session_name}`.",
                ephemeral=True,
            )

        @self.tree.command(name="tail", description="Show recent output from the bound tmux session.")
        @app_commands.describe(lines="number of lines to fetch")
        async def tail(interaction: discord.Interaction, lines: int | None = None) -> None:
            if not await self.access_controller.assert_allowed(interaction):
                return
            binding = self.registry.get(interaction.channel_id)
            if binding is None:
                await interaction.response.send_message(
                    "This channel is not bound. Run `/bind session:<name>` first.",
                    ephemeral=True,
                )
                return
            requested = lines or self.config.default_tail_lines
            capped = min(max(1, requested), self.config.max_tail_lines)
            try:
                output = self.tmux_service.capture_tail(binding.session_name, capped)
            except TmuxError as exc:
                await interaction.response.send_message(
                    f"Failed to capture `{binding.session_name}`: {exc}",
                    ephemeral=True,
                )
                return
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                f"Recent output from `{binding.session_name}` ({capped} lines max)\n{_render_code_block(output)}",
                ephemeral=True,
            )

        @self.tree.command(name="status", description="Show binding and tmux session status for this channel.")
        async def status(interaction: discord.Interaction) -> None:
            if not await self.access_controller.assert_allowed(interaction):
                return
            binding = self.registry.get(interaction.channel_id)
            if binding is None:
                await interaction.response.send_message(
                    "This channel is not bound.",
                    ephemeral=True,
                )
                return
            tmux_status = self.tmux_service.get_status(binding.session_name)
            await interaction.response.send_message(
                "\n".join(
                    [
                        f"Channel: <#{binding.channel_id}>",
                        f"Session: `{binding.session_name}`",
                        f"Auto-send: `{binding.auto_send}`",
                        f"Tmux exists: `{tmux_status.exists}`",
                        f"Bound by: <@{binding.bound_by}>",
                        f"Bound at: `{binding.bound_at}`",
                        f"Last used at: `{binding.last_used_at}`",
                    ]
                ),
                ephemeral=True,
            )
