---
icon: lucide/rocket
---

# Getting Started

From zero to driving a tmux session from Discord or Telegram in ~5 minutes.

## Prerequisites

- Python 3.11+
- `tmux` installed (`brew install tmux` / `apt install tmux`)
- A Discord and/or Telegram account where you can create a bot

You only need one of the two; both is fine.

## 1. Create a bot

Pick the platform(s) you want to use, follow the dedicated setup page once, then come back here:

- [Discord Setup](platforms/discord.md) — Developer Portal, bot token, user ID
- [Telegram Setup](platforms/telegram.md) — BotFather, user ID, group privacy

Each page leaves you with the credentials you'll paste in step 3.

## 2. Install

```bash
pipx install tetherly
# or, with uv:
uv tool install tetherly
```

To upgrade later:

```bash
pipx upgrade tetherly
# or:
uv tool upgrade tetherly
```

`~/.tetherly/.env` and `~/.tetherly/state.json` live outside the install location, so upgrades preserve config and bindings. Restart the bot after upgrading (`Ctrl-C`, then `tetherly` again).

## 3. Initialize

```bash
tetherly init
```

This is interactive. It will:

- Ask whether to enable Discord, Telegram, or both, and prompt for the relevant tokens and user IDs.
- Write `~/.tetherly/.env` (chmod 600).
- Ask where to install **Codex** hooks, then ask the same for **Claude Code** hooks. **Global** = fires everywhere; **Project** = run the install command per project; **Skip** = decide later.

| Hook scope | Codex writes | Claude Code writes | Effect |
| --- | --- | --- | --- |
| **Global** | `~/.codex/hooks.json`, `~/.codex/config.toml` | `~/.claude/settings.json` | Hooks fire in every project automatically. |
| **Project** | nothing now | nothing now | Run `tetherly install-hooks` / `tetherly install-claude-hooks` per project. |
| **Skip** | nothing | nothing | No hooks installed. You can run the install commands later. |

Global is safe by default because [hook gating](reference/architecture.md#agent-cli-hook-gating-why-global-hooks-stay-quiet) means only `/bind`-ed sessions actually produce notifications.

## 4. Start the bot

```bash
tetherly
```

A single process runs whichever bots you configured. Leave it running.

## 5. Bind a tmux session

In a second terminal:

```bash
tmux new -s work
```

Then in your chat:

```text
# Discord
/bind session:work
/config auto_send:true

# Telegram
/bind work
/config on
```

That's it. Now:

- Anything you type in that chat goes to the `work` tmux session, followed by Enter.
- `/send`, `/key`, `/tail`, `/status` all work — see [Command Reference](reference/commands.md).
- Codex (Stop, PermissionRequest) and Claude Code (Stop, Notification) alerts and `/status` / `/tail` responses include inline buttons — tap instead of typing.
- From inside the tmux session, `tetherly send --message "done"` posts back to the chat — see [Agent Send](reference/agent-send.md).

## Changing config later

Anything you entered in step 3 lives in `~/.tetherly/.env`:

- `tetherly config show` — print current values (tokens masked).
- `tetherly config edit` — open the file in `$EDITOR`.
- `tetherly init` — re-run the guided flow; existing values appear as defaults.

Restart the bot after any change.

## Where to next

- [Command Reference](reference/commands.md) — every slash command on both platforms.
- [Architecture](reference/architecture.md) — operating model, gating rules, session resolution.
- [Agent Send](reference/agent-send.md) — how `tetherly send` resolves which chat to post to.
- [Security](security.md) — locking the bot down to specific users, guilds, chats, and roles.
