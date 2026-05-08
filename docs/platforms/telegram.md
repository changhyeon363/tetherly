---
icon: lucide/send
---

# Telegram Setup

Step-by-step setup for the Telegram side of tetherly. The Discord-equivalent is in [Discord Setup](discord.md).

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

> Slash commands work either way; privacy mode only affects whether the bot can read non-command plain text. See [Security → Telegram](../security.md#telegram) for why DM-only is recommended.

## (Recommended) Disable group invites entirely

If you only ever use the bot in DMs, lock that in at the BotFather level so no one — not even you, by accident — can drop the bot into a group:

1. Open @BotFather → `/mybots` → pick your bot.
2. **Bot Settings → Allow Groups? → Turn off**.

With this off, the "Add to Group" option is greyed out for every Telegram user. To use the bot in a group later, flip it back on — and remember to also configure privacy mode and `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS` before doing so.

This is the Telegram equivalent of Discord's "Public Bot off". See [Security → Telegram](../security.md#telegram) for the full layered model.

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
tetherly        # runs whichever bots are configured
```

In your Telegram chat with the bot:

```text
/bind work
/config on        # optional: forward plain text → tmux without /send
/status
```

When you type `/`, Telegram shows an autocomplete menu of the bot's commands (registered automatically on startup via the [setMyCommands](https://core.telegram.org/bots/api#setmycommands) API).

## Argument syntax

Telegram uses **positional arguments** (`/bind work`, `/config on`). The full command list — same set as Discord, just different syntax — is in [Command Reference](../reference/commands.md).

When you pick a command from the `/` autocomplete that needs an argument, the bot replies with a one-line ForceReply prompt and your input area auto-opens. See [Command Reference → Filling in arguments via reply](../reference/commands.md#telegram-filling-in-arguments-via-reply).

## Access control

| Variable | Purpose |
| --- | --- |
| `TETHERLY_TELEGRAM_ALLOWED_USER_IDS` | User IDs that can run commands. Empty list = no one can run anything (fail-closed). |
| `TETHERLY_TELEGRAM_ALLOWED_CHAT_IDS` | (Optional) restrict to specific chat IDs. |

**Access denials are silent**: a non-allowlisted user gets no reply at all (one log line server-side). Full rationale and security guidance: [Security → Telegram](../security.md#telegram).

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Bot ignores your commands silently | Your user ID isn't in `TETHERLY_TELEGRAM_ALLOWED_USER_IDS` | Add it via `tetherly config edit` and restart the bot |
| Plain text in a group is ignored even with `/config on` | Bot privacy mode still on | BotFather → `/mybots` → Group Privacy → Turn off |
| Bot doesn't respond at all | Bot process not running, or wrong token | Confirm `tetherly` is running and `tetherly config show` looks right |
| Tapping `/send` from autocomplete sends a bare command and the reply UI doesn't open | Old Telegram client cached an obsolete prompt; or the client can't render ForceReply | Update the client; as a fallback, type the argument inline (`/send hello`) |
| No autocomplete menu when typing `/` | `setMyCommands` call failed at startup | Check the bot logs for a `setMyCommands errored` warning; usually transient — restart the bot |
