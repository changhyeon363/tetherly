---
icon: lucide/rocket
---

# Quick Start

From zero to driving a tmux session from Discord or Telegram in ~5 minutes.

## Prerequisites

- Python 3.11+
- `tmux` installed (`brew install tmux` / `apt install tmux`)
- A Discord account where you can create an application/bot **and/or** a Telegram account to talk to [@BotFather](https://t.me/BotFather)

You'll need at least one of the two; both is also fine.

## 1. Create a chat bot

### Discord

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy the token.
3. **Privileged Gateway Intents** → enable **Message Content Intent** (required for plain-text auto-send).
4. **OAuth2 → URL Generator** → check `bot` and `applications.commands`, set permissions to at least **Send Messages** and **Read Messages**, then open the generated URL to invite the bot to your server.

You'll also need your **Discord user ID** (right-click your name with Developer Mode on → *Copy User ID*).

### Telegram

1. DM [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → follow prompts → copy the token.
2. DM [@userinfobot](https://t.me/userinfobot) to learn your numeric Telegram **user ID**.
3. Start a chat with your new bot (or add it to a group). The bot only listens to allowlisted users, so commands from anyone else are silently ignored.

For group chats, privacy mode and chat-ID allowlists, see the dedicated [Telegram setup](telegram-setup.md) page.

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

## 3. Initialize

```bash
tetherly init
```

This is interactive. It will:

- Ask whether to enable Discord, Telegram, or both, and prompt for the relevant tokens and user IDs.
- Write `~/.tetherly/.env` (chmod 600).
- Ask where to install Codex hooks. **Global** = fires everywhere; **Skip** = decide per project.

See [Setup and usage](usage.md) for the full breakdown.

## 4. Start the bot(s)

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

- Anything you type in that chat goes straight to the `work` tmux session, followed by Enter.
- `/send`, `/key`, `/tail`, `/status` work the same in both platforms.
- `/unbind` releases the chat from the session — required before binding the same session somewhere else (a session is globally unique across platforms).
- From inside the tmux session, `tetherly send --message "done"` posts back to the chat — see [Agent replies](agent-replies.md).

## Changing config later

Anything you entered in step 3 lives in `~/.tetherly/.env`:

- `tetherly config show` — print the current values (tokens masked).
- `tetherly config edit` — open the file in `$EDITOR`.
- `tetherly init` — re-run the guided flow; existing values appear as defaults.

Restart the bot after any change.

## Where to next

- [Telegram setup](telegram-setup.md) — full BotFather walkthrough, privacy mode, group chat IDs.
- [Setup and usage](usage.md) — operating model, re-binding behavior, the gating rules that keep global hooks quiet.
- [Agent replies](agent-replies.md) — how `tetherly send` resolves which chat to post to.
- [Security](security.md) — locking the bot down to specific users, guilds, chats, and roles.
