---
icon: lucide/waypoints
---

<p align="center">
  <img src="assets/images/tetherly-icon.png" alt="tetherly icon" width="96" height="96">
</p>

# tetherly

A Discord channel ↔ tmux session bridge for agent-driven workflows.

One bot, many tmux sessions, many Discord channels. `/bind` a channel to a session and Codex (or any agent inside that tmux session) can post status/results back to Discord, while you control the session through Discord slash commands.

## Start here

- **[Quick Start](user/quickstart.md)** — install, create a bot, bind your first channel in ~5 minutes.
- **[Setup and usage](user/usage.md)** — operating model, install modes, command semantics, troubleshooting.
- **[Agent replies](user/agent-replies.md)** — how `tetherly discord-send` works from inside a bound tmux session.
- **[Security](user/security.md)** — restricting which Discord servers and users can drive the bot.

## For contributors

- **[Codex hooks internals](contributing/codex-hooks-internals.md)** — `Stop` / `PermissionRequest` payload schemas, design decisions, installer merge logic.

## Source

- Repository: [github.com/changhyeon363/tetherly](https://github.com/changhyeon363/tetherly)
