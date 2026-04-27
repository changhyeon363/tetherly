---
icon: lucide/cable
---

# co-agent

A Discord channel ↔ tmux session bridge for agent-driven workflows.

One bot, many tmux sessions, many Discord channels. `/bind` a channel to a session and Codex (or any agent inside that tmux session) can post status/results back to Discord, while you control the session through Discord slash commands.

## Start here

- **[Setup and usage](user/usage.md)** — operating model, install modes, command semantics, troubleshooting.
- **[Agent replies](user/agent-replies.md)** — how `co-agent discord-send` works from inside a bound tmux session.
- **[Security](user/security.md)** — restricting which Discord servers and users can drive the bot.

## For contributors

- **[Codex hooks internals](contributing/codex-hooks-internals.md)** — `Stop` / `PermissionRequest` payload schemas, design decisions, installer merge logic.

## Source

- Repository: [github.com/changhyeon363/co-agent](https://github.com/changhyeon363/co-agent)
