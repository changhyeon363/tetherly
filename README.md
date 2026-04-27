# co-agent

Discord channel to tmux session bridge.

## Features

- `/bind session:<name>`: bind the current Discord channel to a tmux session
- `/config auto_send:<true|false>`: enable or disable plain-text auto-send for the current bound channel
- `/send text:<message>`: send text plus Enter into the bound tmux session
- `/key key:<Enter|Escape|Ctrl-C|Ctrl-D|Tab|Up|Down|Left|Right>`: send a special key into the bound tmux session
- `/tail lines:<n>`: fetch recent tmux output
- `/status`: inspect the current binding and tmux session status
- `co-agent discord-send --message <text>`: let an agent inside a bound tmux session send a reply back to Discord
- `co-agent codex-stop`: handle Codex `Stop` hook payloads (stdin) and forward the last assistant message to the bound Discord channel
- `co-agent codex-permission-request`: handle Codex `PermissionRequest` hook payloads (stdin) and forward the approval prompt to the bound Discord channel

## Requirements

- Python 3.11+
- `tmux` installed
- A Discord bot token
- Discord `Message Content Intent` enabled if you use `/config auto_send:true`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Set environment variables:

```bash
export DISCORD_BOT_TOKEN=...
export CO_AGENT_ALLOWED_GUILD_IDS=123456789012345678
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

Recommended Discord workflow:

1. In the target Discord channel, run `/bind session:<name>`.
2. Run `/config auto_send:true`.
3. Type plain messages directly in the channel to send them to the tmux session with Enter.
4. Use `/key` for interactive controls like Escape, Ctrl-C, and arrow keys.

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

## Codex Hooks

This repo enables Codex hooks via [.codex/config.toml](/Users/ch/D/ch-pj/co-agent/.codex/config.toml):

```toml
[features]
codex_hooks = true
```

[.codex/hooks.json](/Users/ch/D/ch-pj/co-agent/.codex/hooks.json) registers two hooks:

- `Stop` runs `./.venv/bin/co-agent codex-stop` when a Codex turn ends. The handler forwards `last_assistant_message` to the bound Discord channel.
- `PermissionRequest` runs `./.venv/bin/co-agent codex-permission-request` when Codex is about to ask for approval. The handler forwards the tool, command/input, and reason to the bound Discord channel. It does not return an `allow`/`deny` decision, so Codex's normal approval prompt still appears.

Both handlers only fire when the active tmux session has `CO_AGENT_NOTIFY_ON_FINISH=1`. `/bind session:<name>` sets that flag automatically.
