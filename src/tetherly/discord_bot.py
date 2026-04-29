from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands

from tetherly.authz import AccessController
from tetherly.config import Config
from tetherly.session_registry import SessionRegistry, SessionRegistryError
from tetherly.telegram_bot import MessageIntent
from tetherly.tmux_service import TmuxError, TmuxService, normalize_session_name

LOGGER = logging.getLogger(__name__)
AUTO_SEND_MAX_LENGTH = 4000


# Raw component-dict builders. The `discord_sender.py` raw HTTP path needs raw
# dicts (no `discord.Client` available there); the bot process attaches the
# same kind of dict via dynamic Views so the button callbacks fire on click.

# Discord button styles: 1=primary 2=secondary 3=success 4=danger
_STYLE_PRIMARY = 1
_STYLE_SECONDARY = 2
_STYLE_SUCCESS = 3
_STYLE_DANGER = 4


def _btn(label: str, style: int, custom_id: str) -> dict[str, Any]:
    return {"type": 2, "style": style, "label": label, "custom_id": custom_id}


def _action_row(buttons: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": 1, "components": buttons}


def components_for_intent(intent: MessageIntent) -> list[dict[str, Any]] | None:
    if intent == MessageIntent.STOP:
        return [
            _action_row(
                [
                    _btn("⏎ Enter", _STYLE_PRIMARY, "tetherly:key:enter"),
                    _btn("📜 Tail", _STYLE_SECONDARY, "tetherly:tail"),
                    _btn("🛑 Ctrl-C", _STYLE_DANGER, "tetherly:key:ctrl-c"),
                ]
            )
        ]
    if intent == MessageIntent.PERMISSION:
        return [
            _action_row(
                [
                    _btn("✅ Yes", _STYLE_SUCCESS, "tetherly:key:enter"),
                    _btn("❌ No", _STYLE_DANGER, "tetherly:key:ctrl-c"),
                    _btn("📜 Tail", _STYLE_SECONDARY, "tetherly:tail"),
                ]
            )
        ]
    return None


def components_for_status() -> list[dict[str, Any]]:
    return [
        _action_row(
            [
                _btn("🔄 Refresh", _STYLE_PRIMARY, "tetherly:status"),
                _btn("📜 Tail", _STYLE_SECONDARY, "tetherly:tail"),
            ]
        ),
        _action_row(
            [
                _btn("⏎ Enter", _STYLE_PRIMARY, "tetherly:key:enter"),
                _btn("🛑 Ctrl-C", _STYLE_DANGER, "tetherly:key:ctrl-c"),
            ]
        ),
    ]


def components_for_tail() -> list[dict[str, Any]]:
    return [
        _action_row(
            [
                _btn("🔄 Refresh", _STYLE_PRIMARY, "tetherly:tail"),
                _btn("⏎ Enter", _STYLE_PRIMARY, "tetherly:key:enter"),
                _btn("🛑 Ctrl-C", _STYLE_DANGER, "tetherly:key:ctrl-c"),
            ]
        )
    ]


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


class TetherlyBot(discord.Client):
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
        # Register the persistent dispatcher so button clicks on messages sent
        # via raw HTTP (Codex hooks) get routed to our handlers across restarts.
        self.add_view(_TetherlyDispatchView(self))
        if self.config.test_guild_id is not None:
            guild = discord.Object(id=self.config.test_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            LOGGER.info("synced commands to guild %s", self.config.test_guild_id)
            return
        await self.tree.sync()

    async def on_ready(self) -> None:
        LOGGER.info("bot ready as %s", self.user)

    def _format_status_message(self, binding) -> str:
        tmux_status = self.tmux_service.get_status(binding.session_name)
        if tmux_status.exists:
            headline = f"🟢 Active — tmux session `{binding.session_name}` is alive"
        else:
            headline = (
                f"🔴 tmux session `{binding.session_name}` is GONE — "
                "run `/bind session:<name>` to reconnect"
            )
        return "\n".join(
            [
                headline,
                f"Channel: <#{binding.channel_id}>",
                f"Auto-send: `{binding.auto_send}`",
                f"Bound by: <@{binding.bound_by}>",
                f"Bound at: `{binding.bound_at}`",
                f"Last used at: `{binding.last_used_at}`",
            ]
        )

    def _format_tail_message(self, binding, capped: int, output: str) -> str:
        return (
            f"Recent output from `{binding.session_name}` ({capped} lines max)\n"
            f"{_render_code_block(output)}"
        )

    async def _handle_button_action(
        self, interaction: discord.Interaction, action: str
    ) -> None:
        if not self.access_controller.is_allowed(interaction):
            await interaction.response.send_message(
                "You are not allowed to use this command.",
                ephemeral=True,
            )
            return
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "Channel context missing.", ephemeral=True
            )
            return
        binding = self.registry.get(interaction.channel_id)
        if binding is None:
            await interaction.response.send_message(
                "This channel is not bound.", ephemeral=True
            )
            return

        if action.startswith("key:"):
            key = action.split(":", 1)[1]
            try:
                self.tmux_service.send_key(binding.session_name, key)
            except TmuxError as exc:
                await interaction.response.send_message(
                    f"Failed to send `{key}`: {exc}", ephemeral=True
                )
                return
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                f"Sent `{key}` to `{binding.session_name}`.", ephemeral=True
            )
            return

        if action == "tail":
            capped = min(
                max(1, self.config.default_tail_lines), self.config.max_tail_lines
            )
            try:
                output = self.tmux_service.capture_tail(binding.session_name, capped)
            except TmuxError as exc:
                await interaction.response.send_message(
                    f"Failed to capture: {exc}", ephemeral=True
                )
                return
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                self._format_tail_message(binding, capped, output),
                view=view_for_tail(self),
                ephemeral=True,
            )
            return

        if action == "status":
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                self._format_status_message(binding),
                view=view_for_status(self),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Unknown action `{action}`.", ephemeral=True
        )

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
                "TETHERLY_SESSION",
                session_name,
            )
            self.tmux_service.set_session_environment(
                session_name,
                "TETHERLY_NOTIFY_ON_FINISH",
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
            name="unbind",
            description="Release this channel from its tmux session binding.",
        )
        async def unbind(interaction: discord.Interaction) -> None:
            if not await self.access_controller.assert_allowed(interaction):
                return
            binding = self.registry.get(interaction.channel_id)
            if binding is None:
                await interaction.response.send_message(
                    "This channel is not bound.",
                    ephemeral=True,
                )
                return
            try:
                self.tmux_service.set_session_environment(
                    binding.session_name, "TETHERLY_NOTIFY_ON_FINISH", ""
                )
            except TmuxError:
                pass
            self.registry.unbind(interaction.channel_id)
            await interaction.response.send_message(
                f"Unbound this channel from `{binding.session_name}`.",
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

        @self.tree.command(name="key", description="Send a special key into the bound tmux session.")
        @app_commands.describe(key="special key to send")
        @app_commands.choices(
            key=[
                app_commands.Choice(name="Enter", value="enter"),
                app_commands.Choice(name="Escape", value="esc"),
                app_commands.Choice(name="Ctrl-C", value="ctrl-c"),
                app_commands.Choice(name="Ctrl-D", value="ctrl-d"),
                app_commands.Choice(name="Tab", value="tab"),
                app_commands.Choice(name="Up", value="up"),
                app_commands.Choice(name="Down", value="down"),
                app_commands.Choice(name="Left", value="left"),
                app_commands.Choice(name="Right", value="right"),
            ]
        )
        async def key(interaction: discord.Interaction, key: app_commands.Choice[str]) -> None:
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
                self.tmux_service.send_key(binding.session_name, key.value)
            except TmuxError as exc:
                await interaction.response.send_message(
                    f"Failed to send `{key.name}` to `{binding.session_name}`: {exc}",
                    ephemeral=True,
                )
                return
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                f"Sent `{key.name}` to `{binding.session_name}`.",
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
                self._format_tail_message(binding, capped, output),
                view=view_for_tail(self),
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
            await interaction.response.send_message(
                self._format_status_message(binding),
                view=view_for_status(self),
                ephemeral=True,
            )

        for alias_cmd, key_value in _DISCORD_KEY_ALIASES.items():
            self._register_key_alias(alias_cmd, key_value)

    def _register_key_alias(self, alias_cmd: str, key_value: str) -> None:
        description = f"Send {key_value} to the bound tmux session"

        @self.tree.command(name=alias_cmd, description=description)
        async def alias(interaction: discord.Interaction) -> None:
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
                self.tmux_service.send_key(binding.session_name, key_value)
            except TmuxError as exc:
                await interaction.response.send_message(
                    f"Failed to send `{key_value}`: {exc}",
                    ephemeral=True,
                )
                return
            self.registry.touch(interaction.channel_id)
            await interaction.response.send_message(
                f"Sent `{key_value}` to `{binding.session_name}`.",
                ephemeral=True,
            )


_DISCORD_KEY_ALIASES = {
    "enter": "enter",
    "esc": "esc",
    "ctrlc": "ctrl-c",
    "ctrld": "ctrl-d",
    "tab": "tab",
}


# View classes ---------------------------------------------------------------

def _make_button(bot: "TetherlyBot", label: str, style: int, custom_id: str) -> discord.ui.Button:
    """Build a Button whose callback delegates back to the bot's action handler."""
    discord_style = {
        _STYLE_PRIMARY: discord.ButtonStyle.primary,
        _STYLE_SECONDARY: discord.ButtonStyle.secondary,
        _STYLE_SUCCESS: discord.ButtonStyle.success,
        _STYLE_DANGER: discord.ButtonStyle.danger,
    }[style]
    button = discord.ui.Button(label=label, style=discord_style, custom_id=custom_id)
    action = custom_id.removeprefix("tetherly:")

    async def _callback(interaction: discord.Interaction) -> None:
        await bot._handle_button_action(interaction, action)

    button.callback = _callback
    return button


def view_for_intent(bot: "TetherlyBot", intent: MessageIntent) -> discord.ui.View | None:
    components = components_for_intent(intent)
    if components is None:
        return None
    return _components_to_view(bot, components)


def view_for_status(bot: "TetherlyBot") -> discord.ui.View:
    return _components_to_view(bot, components_for_status())


def view_for_tail(bot: "TetherlyBot") -> discord.ui.View:
    return _components_to_view(bot, components_for_tail())


def _components_to_view(
    bot: "TetherlyBot", rows: list[dict[str, Any]]
) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for row_index, row in enumerate(rows):
        for raw in row.get("components", []):
            button = _make_button(
                bot,
                label=raw["label"],
                style=raw["style"],
                custom_id=raw["custom_id"],
            )
            button.row = row_index
            view.add_item(button)
    return view


class _TetherlyDispatchView(discord.ui.View):
    """Persistent dispatcher: button clicks on raw-HTTP-sent messages route here."""

    def __init__(self, bot: "TetherlyBot") -> None:
        super().__init__(timeout=None)
        self._bot = bot
        for custom_id, (label, style) in _DISPATCH_BUTTONS.items():
            button = _make_button(bot, label=label, style=style, custom_id=custom_id)
            self.add_item(button)


# Every custom_id we emit must appear here so the persistent dispatcher matches it.
# Labels/styles only matter if the View is ever rendered directly (it isn't).
_DISPATCH_BUTTONS: dict[str, tuple[str, int]] = {
    "tetherly:key:enter": ("Enter", _STYLE_PRIMARY),
    "tetherly:key:esc": ("Esc", _STYLE_SECONDARY),
    "tetherly:key:ctrl-c": ("Ctrl-C", _STYLE_DANGER),
    "tetherly:key:ctrl-d": ("Ctrl-D", _STYLE_SECONDARY),
    "tetherly:key:tab": ("Tab", _STYLE_SECONDARY),
    "tetherly:tail": ("Tail", _STYLE_SECONDARY),
    "tetherly:status": ("Status", _STYLE_PRIMARY),
}
