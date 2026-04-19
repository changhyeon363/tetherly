# co-agent

Discord channel to tmux session bridge.

## Features

- `/bind session:<name>`: bind the current Discord channel to a tmux session
- `/send text:<message>`: send text plus Enter into the bound tmux session
- `/tail lines:<n>`: fetch recent tmux output
- `/status`: inspect the current binding and tmux session status
- `co-agent discord-send --message <text>`: let an agent inside a bound tmux session send a reply back to Discord
- `co-agent codex-notify <payload>`: forward Codex notify payloads back to the bound Discord channel

## Requirements

- Python 3.11+
- `tmux` installed
- A Discord bot token

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set environment variables:

```bash
export DISCORD_BOT_TOKEN=...
export CO_AGENT_ALLOWED_ROLE_IDS=1234567890,2345678901
export CO_AGENT_ALLOWED_USER_IDS=3456789012
```

Optional configuration:

```bash
export CO_AGENT_STATE_PATH=.co-agent/state.json
export CO_AGENT_TEST_GUILD_ID=123456789012345678
export CO_AGENT_DEFAULT_TAIL_LINES=40
export CO_AGENT_MAX_TAIL_LINES=200
export CO_AGENT_LOG_LEVEL=INFO
```

`CO_AGENT_TEST_GUILD_ID` is recommended for local testing because guild command sync is immediate.

You can also put the same values in a local `.env` file. The app will load `.env` automatically on startup.

Run:

```bash
co-agent
```

Send a Discord message from a local agent process running inside a bound tmux session:

```bash
co-agent discord-send --message "작업 끝났습니다"
```

Or read the message from standard input:

```bash
cat result.txt | co-agent discord-send --stdin
```

If you need to send from outside tmux, you can still pass the session explicitly:

```bash
co-agent discord-send --session t1 --message "작업 끝났습니다"
```

## Codex Notify

This repo includes a local [config.toml](/Users/ch/D/ch-pj/co-agent/.codex/config.toml) for Codex:

```toml
notify = ["./.venv/bin/co-agent", "codex-notify"]

[features]
codex_hooks = true
```

When you run `/bind session:<name>`, the bot stores `CO_AGENT_NOTIFY_ON_FINISH=1` in that tmux session.
After a Codex turn completes in that session, `co-agent codex-notify` forwards the last assistant message to the bound Discord channel.

This repo also includes [hooks.json](/Users/ch/D/ch-pj/co-agent/.codex/hooks.json) with a `PermissionRequest` hook.
It sends a Discord alert when Codex asks for approval, but it does not auto-allow or auto-deny anything.
