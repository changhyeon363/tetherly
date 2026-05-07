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
| **Quick keys** | `/enter` `/esc` `/ctrlc` `/ctrld` `/tab` (no arguments) |

A tmux session is **globally unique across platforms** — bound to one Discord channel **or** one Telegram chat, never both. Run `/unbind` first to move it.

## Inline buttons

The bot attaches inline buttons to alerts and to `/status` / `/tail`, so you rarely need to type slash commands at all:

| Trigger | Buttons |
| --- | --- |
| Codex Stop alert ("작업이 끝났습니다") | `[Enter] [Tail] [Stop]` |
| Codex PermissionRequest alert | `[Yes] [No] [Tail]` (Yes = Enter, No = Ctrl-C) |
| `/status` | `[Refresh] [Tail] [Enter] [Stop]` |
| `/tail` | `[Refresh] [Enter] [Stop]` |

Tap a button to send the action; **Refresh** edits the same message in place via `editMessageText`, so your chat doesn't pile up duplicate snapshots. **Stop** maps to `Ctrl-C`. There is no permanent reply keyboard — the input area stays clean.

## Filling in arguments via reply

Telegram's slash autocomplete sends a command **immediately** when you tap it, so picking `/send` from the menu would normally arrive with no text. The bot handles this by replying with a one-line prompt (a [ForceReply](https://core.telegram.org/bots/api#forcereply) message) — your input area auto-opens as a reply, and whatever you type next becomes the command's argument:

```text
You:  /send                     ← tapped from the autocomplete menu
Bot:  Reply to this message with the text to send (will be followed by Enter).
You:  ls                        ← typed as the auto-opened reply
Bot:  Sent to `t1`.
```

Same flow for `/bind`, `/config`, `/key` when picked from autocomplete. Slash commands you type fully (with the argument inline, e.g. `/send hello`) go through directly without the prompt step. `/tail`, `/status`, `/unbind`, `/help`, and the quick-key aliases never need an argument.

## Access denials are silent

When a non-allowlisted user (anyone whose ID isn't in `TETHERLY_TELEGRAM_ALLOWED_USER_IDS`) tries a command — slash command, button click, or anything else — **the bot does not reply at all**. It logs a single line server-side and ignores the input. This is intentional: a "permission denied" reply would advertise the bot's existence and invite further probing. Strangers who stumble onto your bot username see what looks like a dead bot.

Practically: if you tap a button or send a command and the bot doesn't react, double-check that your numeric user ID is on the allowlist via `tetherly config show`.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Bot ignores your commands silently | Your user ID isn't in `TETHERLY_TELEGRAM_ALLOWED_USER_IDS` | Add it via `tetherly config edit` and restart the bot |
| Plain text in a group is ignored even with `/config on` | Bot privacy mode still on | BotFather → `/mybots` → Group Privacy → Turn off |
| Bot doesn't respond at all | Bot process not running, or wrong token | Confirm `tetherly` is running and `tetherly config show` looks right |
| `/bind` errors with `"already bound to ... channel X"` | Session already bound somewhere (Discord or Telegram) | `/unbind` in chat X, then re-bind |
| Tapping `/send` from autocomplete just sends a bare command and the reply UI doesn't open | Old Telegram client cached an obsolete prompt; or you're on a client that can't render ForceReply | Update the client; as a fallback, type the argument inline (`/send hello`) |
| No autocomplete menu when typing `/` | `setMyCommands` call failed at startup | Check the bot logs for a `setMyCommands errored` warning; usually a transient network issue, restart the bot |
