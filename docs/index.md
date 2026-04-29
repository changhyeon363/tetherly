---
icon: lucide/waypoints
---

<p align="center">
  <img src="assets/images/tetherly-icon.png" alt="tetherly icon" width="96" height="96">
</p>

# tetherly

A Discord / Telegram chat ↔ tmux session bridge for agent-driven workflows.

One process, optional Discord and Telegram bots, many tmux sessions, many chats. `/bind` a chat to a session and Codex (or any agent inside that tmux session) can post status/results back to the chat, while you control the session through slash commands.

## Start here

- **[Quick Start](user/quickstart.md)** — install, create a bot, bind your first chat in ~5 minutes.
- **[Telegram setup](user/telegram-setup.md)** — BotFather, privacy mode, group chats, troubleshooting.
- **[Setup and usage](user/usage.md)** — operating model, install modes, command semantics, troubleshooting.
- **[Agent replies](user/agent-replies.md)** — how `tetherly send` routes replies from inside a bound tmux session.
- **[Security](user/security.md)** — restricting which servers, chats, and users can drive the bot.

## For contributors

- **[Codex hooks internals](contributing/codex-hooks-internals.md)** — `Stop` / `PermissionRequest` payload schemas, design decisions, installer merge logic.

## Source

- Repository: [github.com/changhyeon363/tetherly](https://github.com/changhyeon363/tetherly)
