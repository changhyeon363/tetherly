---
icon: lucide/send
---

# Telegram Setup

Step-by-step setup for the Telegram side of tetherly. The Discord-equivalent is in [Quick Start](quickstart.md).

## 1. Create a bot via @BotFather

1. On Telegram, open a chat with [@BotFather](https://t.me/BotFather).
2. Send `/newbot`.
3. Pick a **display name** (anything, e.g. `tetherly-cy`).
4. Pick a **username** — must end in `bot` and be globally unique (e.g. `tetherly_cy_bot`).
5. BotFather replies with an HTTP API token like `1234567890:AAH...`. **This is the secret your bot uses to authenticate** — treat it like a password.

> 🔐 If a token leaks, talk to @BotFather → `/revoke` to invalidate it and get a new one.

## 2. Find your numeric user ID

The bot will only respond to allowlisted user IDs.

- Open a chat with [@userinfobot](https://t.me/userinfobot) and send any message. It replies with your numeric user ID.
- (Or any equivalent: @getidsbot, @RawDataBot, etc.)

Save this number for step 5.

## 3. (Group chat only) Disable privacy mode

By default, Telegram bots in groups **only see messages that start with `/`** — they don't see plain text.

If you want to use **`/config on` (auto-send)** in a group chat, you need to turn privacy mode off:

1. Open @BotFather → `/mybots` → pick your bot.
2. **Bot Settings → Group Privacy → Turn off**.

In **private (DM) chats** you don't need this — the bot can already see all your messages.

> Slash commands themselves work either way; privacy mode only affects whether the bot can read non-command plain text.

## 4. (Optional) Find a group chat ID

If you want to restrict the bot to specific group chats via `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS`:

1. Add the bot to the group.
2. Send any message in that group.
3. Forward the message to [@userinfobot](https://t.me/userinfobot) — it shows the **chat ID** (a negative number for groups, e.g. `-1001234567890`).

Leave `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS` blank if you don't want a chat-level restriction (user-level allowlist alone is usually enough).

## 5. Run `tetherly init`

```bash
tetherly init
```

When prompted:

- **Enable Telegram bot?** → `y`
- **Token** → paste the token from step 1 (input is hidden)
- **User ID(s)** → your numeric user ID from step 2 (comma-separate if multiple)
- **Telegram chat ID(s)** → optional; leave blank or paste the chat IDs from step 4

This writes `TELEGRAM_BOT_TOKEN`, `TETHERLY_TELEGRAM_ALLOWED_USER_IDS`, and (optionally) `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS` to `~/.tetherly/.env`.

## 6. Start the bot and bind a session

```bash
tetherly        # runs Discord and/or Telegram bots, whichever are configured
```

In your Telegram chat with the bot:

```text
/bind work
/config on        # optional: forward plain text → tmux without /send
/status
```

When you type `/`, Telegram should now show an autocomplete menu of the bot's commands (registered automatically on startup via the [setMyCommands](https://core.telegram.org/bots/api#setmycommands) API).

## Command reference

Same commands as the Discord side, with Telegram-flavored argument syntax:

| Command | Telegram form |
| --- | --- |
| Bind chat to session | `/bind <session-name>` |
| Release this chat | `/unbind` |
| Toggle auto-send | `/config on` / `/config off` |
| Send text + Enter | `/send <text>` |
| Send special key | `/key Enter` (or `Escape`, `Ctrl-C`, `Ctrl-D`, `Tab`, `Up`, `Down`, `Left`, `Right`) |
| Recent output | `/tail` or `/tail 80` |
| Status | `/status` |
| Help | `/help` |

A tmux session is **globally unique across platforms** — bound to one Discord channel **or** one Telegram chat, never both. Run `/unbind` first to move it.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Bot replies "You are not allowed to use this command." | Your user ID isn't in `TETHERLY_TELEGRAM_ALLOWED_USER_IDS` | Add it via `tetherly config edit` and restart the bot |
| Plain text in a group is ignored even with `/config on` | Bot privacy mode still on | BotFather → `/mybots` → Group Privacy → Turn off |
| Bot doesn't respond at all | Bot process not running, or wrong token | Confirm `tetherly` is running and `tetherly config show` looks right |
| `/bind` errors with `"already bound to ... channel X"` | Session already bound somewhere (Discord or Telegram) | `/unbind` in chat X, then re-bind |
| No autocomplete menu when typing `/` | `setMyCommands` call failed at startup | Check the bot logs for a `setMyCommands errored` warning; usually a transient network issue, restart the bot |
