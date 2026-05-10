---
icon: lucide/waypoints
---

<p align="center">
  <img src="assets/images/tetherly-icon.png" alt="tetherly icon" width="96" height="96">
</p>

# tetherly

A Discord / Telegram chat ↔ tmux session bridge for agent-driven workflows.

One process, optional Discord and Telegram bots, many tmux sessions, many chats. `/bind` a chat to a session and Codex, Claude Code, or any agent inside that tmux session can post status/results back to the chat, while you control the session through slash commands.

## Start here

- **[Getting Started](getting-started.md)** — install, create a bot, bind your first chat in ~5 minutes.

## Platforms

- **[Discord Setup](platforms/discord.md)** — Developer Portal, bot token, intents, IDs.
- **[Telegram Setup](platforms/telegram.md)** — BotFather, privacy mode, group chats.

## Reference

- **[Command Reference](reference/commands.md)** — every slash command, on both platforms.
- **[Architecture](reference/architecture.md)** — operating model, hook gating, session resolution, file paths.
- **[Agent Send](reference/agent-send.md)** — how `tetherly send` routes replies from inside a bound tmux session.
- **[Security](security.md)** — restricting which servers, chats, and users can drive the bot.

## For contributors

- **[Releasing](contributing/releasing.md)** — tag flow, PyPI Trusted Publishing, versioning.
- **[Codex Hooks Internals](contributing/codex-hooks-internals.md)** — `Stop` / `PermissionRequest` payload schemas, design decisions, installer merge logic.
- **[Claude Code Hooks Internals](contributing/claude-code-hooks-internals.md)** — `Stop` / `Notification` payload schemas, settings.json layout, design decisions.

## Source

- Repository: [github.com/changhyeon363/tetherly](https://github.com/changhyeon363/tetherly)
