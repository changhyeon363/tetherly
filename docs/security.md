---
icon: lucide/shield
---

# Security

tetherly restricts command execution by user (and optionally chat/server) on both Discord and Telegram. Both platforms are **fail-closed**: if no users are allowlisted, no one can run commands.

## Discord

### 1. Bot install protection

In the Discord Developer Portal, keep **Public Bot** turned off. Otherwise anyone could add your bot to their server.

### 2. Server (guild) restriction

`TETHERLY_ALLOWED_GUILD_IDS` lists Discord servers in which commands are accepted. `/bind`, `/send`, `/tail`, `/status` are rejected anywhere else.

This restricts **command execution**, not bot installation. Pair it with "Public Bot off" for layered defense.

### 3. User restriction

`TETHERLY_ALLOWED_USER_IDS` lists Discord users that can run commands. Even within an allowed server, only these users are accepted.

### Recommended `.env`

```env
DISCORD_BOT_TOKEN=...
TETHERLY_ALLOWED_GUILD_IDS=YOUR_GUILD_ID
TETHERLY_ALLOWED_USER_IDS=YOUR_USER_ID
TETHERLY_TEST_GUILD_ID=YOUR_GUILD_ID    # dev-only: faster slash command sync
```

### Operational tips

- Keep **Public Bot** off in the Developer Portal.
- `TETHERLY_ALLOWED_GUILD_IDS` should contain only your own server(s).
- `TETHERLY_ALLOWED_USER_IDS` should contain only your own user ID.
- Avoid `TETHERLY_ALLOWED_ROLE_IDS` unless you actually need role-based access — minimize the surface.

## Telegram

### 1. Token

`TELEGRAM_BOT_TOKEN` is the entirety of bot authentication. If it leaks, anyone can act as the bot — and they can also steal your incoming updates (Telegram only allows one polling client per token).

If a token leaks: [@BotFather](https://t.me/BotFather) → `/revoke` → get a new token → `tetherly config edit` → restart the bot.

### 2. User restriction

`TETHERLY_TELEGRAM_ALLOWED_USER_IDS` lists Telegram users that can run commands.

- **Empty list = no one can run anything** (fail-closed, same as Discord).
- A non-allowlisted user's commands and button clicks get **no reply** — the bot logs one line server-side and ignores the input. A "permission denied" reply would advertise the bot's existence and invite further probing, so silence is intentional.
- Practical consequence: if you tap a button or send a command and the bot doesn't react, double-check that your numeric user ID is on the allowlist via `tetherly config show`.

### 3. Chat restriction (optional)

`TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS` lists chat IDs in which commands are accepted (your user ID for DMs, a negative number for groups). Empty = user allowlist alone is the limiter, which is usually enough for personal bots.

### 4. Privacy mode

If BotFather's privacy mode is **on** (the default), the bot in groups only receives messages that start with `/`.

To use `/config on` (auto-send) in a group, you must turn privacy mode off — but **a privacy-off bot receives every message in the group**. Prefer DM-only operation when possible. Setup steps: [Telegram Setup → Disable privacy mode](platforms/telegram.md#3-group-chat-only-disable-privacy-mode).

### Recommended `.env`

```env
TELEGRAM_BOT_TOKEN=...                                  # from @BotFather
TETHERLY_TELEGRAM_ALLOWED_USER_IDS=YOUR_USER_ID
# TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS=YOUR_CHAT_ID       # only when needed
```

### Operational tips

- Prefer DMs over groups — no privacy mode override needed.
- If you must use a group, also set `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS`.
- Never commit tokens to git. `~/.tetherly/.env` is `chmod 600` automatically.
