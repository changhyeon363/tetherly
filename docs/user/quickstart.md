---
icon: lucide/rocket
---

# Quick Start

From zero to driving a tmux session from Discord in ~5 minutes.

## Prerequisites

- Python 3.11+
- `tmux` installed (`brew install tmux` / `apt install tmux`)
- A Discord account where you can create an application/bot

## 1. Create a Discord bot

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy the token. Keep it somewhere safe; you'll paste it in step 3.
3. **Privileged Gateway Intents** → enable **Message Content Intent** (only required if you want plain-text auto-send via `/config auto_send:true`).
4. **OAuth2 → URL Generator** → check `bot` and `applications.commands`, set permissions to at least **Send Messages** and **Read Messages**, then open the generated URL to invite the bot to your server.

You'll also need your **Discord user ID** (right-click your name with Developer Mode on → *Copy User ID*). The bot will reject commands from anyone not on the allowlist.

## 2. Install

```bash
pipx install tetherly
# or, with uv:
uv tool install tetherly
```

Either way you get an isolated environment with a `tetherly` CLI on your `PATH`.

To upgrade later:

```bash
pipx upgrade tetherly
# or, with uv:
uv tool upgrade tetherly
```

## 3. Initialize

```bash
tetherly init
```

This is interactive. It will:

- Write `~/.tetherly/.env` with your bot token and allowed user IDs (chmod 600).
- Ask where to install Codex hooks. Pick **Global** if you want every project's Codex sessions to notify Discord automatically; **Skip** if you don't use Codex or want to decide per project.

See [Setup and usage](usage.md) for the full breakdown of each choice.

## 4. Start the bot

```bash
tetherly
```

Leave this running. Slash commands won't work until the bot is online.

## 5. Bind a tmux session

In a second terminal:

```bash
tmux new -s work
```

In the Discord channel you want to drive that session from:

```text
/bind session:work
/config auto_send:true
```

That's it. Now:

- Anything you type in that Discord channel goes straight to the `work` tmux session, followed by Enter.
- Use `/send` for explicit control, `/key` for special keys, `/tail` to peek at recent output, `/status` to check the binding.
- From inside the tmux session, `tetherly discord-send --message "done"` posts back to the bound channel — see [Agent replies](agent-replies.md).

## Changing config later

Anything you entered in step 3 lives in `~/.tetherly/.env`. To update it:

- `tetherly config show` — print the current values (token masked).
- `tetherly config edit` — open the file in `$EDITOR`.
- `tetherly init` — re-run the guided flow; existing values appear as defaults, press Enter to keep each one.

Restart the bot after any change.

## Where to next

- [Setup and usage](usage.md) — operating model, re-binding behavior, the gating rules that keep global hooks quiet.
- [Agent replies](agent-replies.md) — how `discord-send` resolves which channel to post to.
- [Security](security.md) — locking the bot down to specific users, guilds, and roles.
