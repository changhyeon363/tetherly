# co-agent

Discord channel ↔ tmux session bridge.

> 📖 **Documentation is in [docs/](docs/) — split into [user docs](docs/user/) (setup, commands, troubleshooting) and [contributing docs](docs/contributing/) (internals).** This README is a quick start.

## Features

- `/bind session:<name>`: bind the current Discord channel to a tmux session
- `/config auto_send:<true|false>`: enable or disable plain-text auto-send for the current bound channel
- `/send text:<message>`: send text plus Enter into the bound tmux session
- `/key key:<Enter|Escape|Ctrl-C|Ctrl-D|Tab|Up|Down|Left|Right>`: send a special key into the bound tmux session
- `/tail lines:<n>`: fetch recent tmux output
- `/status`: inspect the current binding and tmux session status
- `co-agent discord-send --message <text>`: let an agent inside a bound tmux session send a reply back to Discord
- `co-agent codex-stop` / `co-agent codex-permission-request`: Codex hook handlers that forward messages to the bound Discord channel

## Requirements

- Python 3.11+
- `tmux` installed
- A Discord bot token (Message Content Intent enabled if you want plain-text auto-send)

## Setup

Install once on your machine:

```bash
pipx install -e /path/to/co-agent
co-agent init
```

`co-agent init` is interactive. It writes `~/.co-agent/.env` and asks where to install Codex hooks:

- **Global** — writes `~/.codex/hooks.json` once. Hooks fire in every project automatically; nothing per-project.
- **Project** — skip global hooks and run `co-agent install-hooks` inside each project where you want them.
- **Skip** — don't touch Codex hooks.

Then start the bot:

```bash
co-agent
```

That's it. State lives at `~/.co-agent/state.json` so a single bot can serve every project.

### Per-project usage

For each project you want to drive from Discord:

```bash
tmux new -s <session-name>
# inside the bound channel on Discord:
#   /bind session:<session-name>
#   /config auto_send:true
```

If you chose **Project** mode during init, also run once per project:

```bash
cd <project>
co-agent install-hooks
```

`install-hooks` accepts `--global` to (re)install user-level hooks instead.

### Sending from inside a session

```bash
co-agent discord-send --message "작업 끝났습니다"
cat result.txt | co-agent discord-send --stdin
co-agent discord-send --session t1 --message "..."   # explicit session
```

## Configuration

`co-agent init` writes everything you need. Advanced overrides live in `~/.co-agent/.env` or shell env:

| Variable | Default | Notes |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | (required) | Bot token |
| `CO_AGENT_ALLOWED_USER_IDS` | (required) | Comma-separated user IDs |
| `CO_AGENT_ALLOWED_GUILD_IDS` | — | Restrict commands to these guilds |
| `CO_AGENT_ALLOWED_ROLE_IDS` | — | Allow members holding any of these roles |
| `CO_AGENT_TEST_GUILD_ID` | — | Dev guild for instant slash-command sync |
| `CO_AGENT_STATE_PATH` | `~/.co-agent/state.json` | Where bindings are persisted |
| `CO_AGENT_DEFAULT_TAIL_LINES` | `40` | Default `/tail` line count |
| `CO_AGENT_MAX_TAIL_LINES` | `200` | Cap for `/tail` |
| `CO_AGENT_LOG_LEVEL` | `INFO` | Logger verbosity |

A `.env` in the current working directory still overrides `~/.co-agent/.env`.

## Codex hooks

Both hooks only fire when the active tmux session has `CO_AGENT_NOTIFY_ON_FINISH=1` — `/bind` sets that flag automatically, so projects without a binding stay silent even when global hooks are installed.

- `Stop` → `co-agent codex-stop` forwards `last_assistant_message` to the bound channel.
- `PermissionRequest` → `co-agent codex-permission-request` forwards the tool/command/reason. It does not return an `allow`/`deny` decision, so Codex's normal approval prompt still appears.
