<p align="center">
  <img src="docs/assets/images/tetherly-icon.png" alt="tetherly icon" width="96" height="96">
</p>

# tetherly

Discord / Telegram channel ↔ tmux session bridge.

> 📖 **Documentation is in [docs/](docs/) — split into [user docs](docs/user/) (setup, commands, troubleshooting) and [contributing docs](docs/contributing/) (internals).** This README is a quick start.

## Features

Same slash commands work in both Discord and Telegram:

- `/bind <session>`: bind the current chat to a tmux session
- `/unbind`: release this chat from its tmux session
- `/config <auto_send>`: toggle plain-text auto-send (Discord uses `auto_send:true|false`, Telegram uses `/config on|off`)
- `/send <text>`: send text plus Enter into the bound tmux session
- `/key <Enter|Escape|Ctrl-C|Ctrl-D|Tab|Up|Down|Left|Right>`: send a special key
- `/tail [lines]`: fetch recent tmux output
- `/status`: inspect the current binding and tmux session status

CLI helpers (run from inside a tmux session):

- `tetherly send --message <text>`: forward a reply to whichever chat (Discord or Telegram) is bound to the session
- `tetherly codex-stop` / `tetherly codex-permission-request`: Codex hook handlers that route messages to the bound chat

A tmux session is **globally unique across platforms** — it can be bound to one Discord channel **or** one Telegram chat, not both. Run `/unbind` first to move it.

## Requirements

- Python 3.11+
- `tmux` installed
- A Discord bot token and/or a Telegram bot token (at least one)
  - Discord: enable Message Content Intent if you want plain-text auto-send
  - Telegram: created via [@BotFather](https://t.me/BotFather) — full walkthrough in [docs/user/telegram-setup.md](docs/user/telegram-setup.md)

## Setup

Install once on your machine:

```bash
pipx install tetherly
# or: uv tool install tetherly
tetherly init
```

`tetherly init` is interactive. It writes `~/.tetherly/.env` and lets you enable Discord, Telegram, or both. It also asks where to install Codex hooks:

- **Global** — writes `~/.codex/hooks.json` once. Hooks fire in every project automatically.
- **Project** — skip global hooks and run `tetherly install-hooks` inside each project.
- **Skip** — don't touch Codex hooks.

Then start the bot(s):

```bash
tetherly
```

A single process runs whichever bots are configured. State lives at `~/.tetherly/state.json` so one process serves every project.

### Per-project usage

For each project you want to drive from chat:

```bash
tmux new -s <session-name>
# then in the bound chat:
#   /bind <session-name>            (Telegram)
#   /bind session:<session-name>    (Discord)
#   /config on   (Telegram)  /  /config auto_send:true   (Discord)
```

If you chose **Project** mode during init, also run once per project:

```bash
cd <project>
tetherly install-hooks
```

`install-hooks` accepts `--global` to (re)install user-level hooks instead.

### Sending from inside a session

```bash
tetherly send --message "작업 끝났습니다"
cat result.txt | tetherly send --stdin
tetherly send --session t1 --message "..."   # explicit session
```

`tetherly send` automatically routes to whichever chat (Discord or Telegram) the session is bound to. The legacy `tetherly discord-send` is still accepted as an alias.

## Configuration

`tetherly init` writes everything you need. Advanced overrides live in `~/.tetherly/.env` or shell env.

### Discord

| Variable | Default | Notes |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | — | Bot token (required to enable Discord) |
| `TETHERLY_ALLOWED_USER_IDS` | — | Comma-separated user IDs |
| `TETHERLY_ALLOWED_GUILD_IDS` | — | Restrict commands to these guilds |
| `TETHERLY_ALLOWED_ROLE_IDS` | — | Allow members holding any of these roles |
| `TETHERLY_TEST_GUILD_ID` | — | Dev guild for instant slash-command sync |

### Telegram

| Variable | Default | Notes |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — | Bot token from @BotFather (required to enable Telegram) |
| `TETHERLY_TELEGRAM_ALLOWED_USER_IDS` | — | Comma-separated user IDs (required) |
| `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS` | — | Restrict commands to these chats |

### Shared

| Variable | Default | Notes |
| --- | --- | --- |
| `TETHERLY_STATE_PATH` | `~/.tetherly/state.json` | Where bindings are persisted |
| `TETHERLY_DEFAULT_TAIL_LINES` | `40` | Default `/tail` line count |
| `TETHERLY_MAX_TAIL_LINES` | `200` | Cap for `/tail` |
| `TETHERLY_LOG_LEVEL` | `INFO` | Logger verbosity |

A `.env` in the current working directory still overrides `~/.tetherly/.env`. **At least one of `DISCORD_BOT_TOKEN` or `TELEGRAM_BOT_TOKEN` must be set.**

## Codex hooks

Both hooks only fire when the active tmux session has `TETHERLY_NOTIFY_ON_FINISH=1` — `/bind` sets this flag automatically and `/unbind` clears it, so projects without a binding stay silent even when global hooks are installed.

- `Stop` → `tetherly codex-stop` forwards `last_assistant_message` to the bound chat (Discord or Telegram).
- `PermissionRequest` → `tetherly codex-permission-request` forwards the tool/command/reason. It does not return an `allow`/`deny` decision, so Codex's normal approval prompt still appears.
