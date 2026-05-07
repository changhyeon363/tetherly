---
icon: lucide/message-circle
---

# Discord Setup

Step-by-step setup for the Discord side of tetherly. The Telegram-equivalent is in [Telegram Setup](telegram.md).

## 1. Create a bot

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy the token. Treat it like a password.
3. **Privileged Gateway Intents** → enable **Message Content Intent** (required for plain-text auto-send).
4. **OAuth2 → URL Generator** → check `bot` and `applications.commands`, set permissions to at least **Send Messages** and **Read Messages**, then open the generated URL to invite the bot to your server.

For production use, keep **Public Bot** turned off in the Developer Portal so others can't add the bot to their servers.

## 2. Find your IDs

You'll need:

- Your **Discord user ID** — right-click your name with Developer Mode on → *Copy User ID*.
- (Optional) Your **guild (server) ID** — right-click the server icon → *Copy Server ID*. Used to restrict where commands can run.

The bot is **fail-closed**: if no user IDs are allowlisted, no one can run commands.

## 3. Run `tetherly init`

```bash
tetherly init
```

When prompted:

- **Enable Discord bot?** → `y`
- **Token** → paste the token from step 1 (input is hidden)
- **User ID(s)** → your numeric user ID (comma-separate if multiple)
- **Guild ID(s)** → optional; restricts which Discord servers the bot will respond in

This writes `DISCORD_BOT_TOKEN`, `TETHERLY_ALLOWED_USER_IDS`, and (optionally) `TETHERLY_ALLOWED_GUILD_IDS` to `~/.tetherly/.env`.

## 4. Start the bot and bind a session

```bash
tetherly        # runs whichever bots are configured
```

In the Discord channel you want to drive:

```text
/bind session:work
/config auto_send:true   # optional: forward plain text → tmux without /send
/status
```

Slash commands appear in Discord's `/` autocomplete after the bot connects.

## Argument syntax

Discord uses **named options** (`session:`, `auto_send:`). The full command list — same set as Telegram, just different argument syntax — is in [Command Reference](../reference/commands.md).

## Access control

| Variable | Purpose |
| --- | --- |
| `TETHERLY_ALLOWED_USER_IDS` | Discord user IDs that can run commands |
| `TETHERLY_ALLOWED_GUILD_IDS` | Discord servers in which commands are accepted |
| `TETHERLY_ALLOWED_ROLE_IDS` | (Optional) role-based allowlist within allowed guilds |
| `TETHERLY_TEST_GUILD_ID` | Dev-only: faster slash command sync to one guild |

Full security guidance: [Security](../security.md).

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Bot is online but ignores `/bind` | User ID not in `TETHERLY_ALLOWED_USER_IDS` | `tetherly config edit` to add it, then restart the bot |
| `Unknown integration` / commands missing | Slash commands haven't synced yet | Wait a few minutes, or set `TETHERLY_TEST_GUILD_ID` for instant sync during development |
| Plain text isn't auto-sent | `Message Content Intent` not enabled, or `auto_send=false` | Enable the intent in the Developer Portal, then `/config auto_send:true` |
| `/bind` errors with `"already bound to … channel X"` | Session is bound somewhere else (any platform) | `/unbind` in chat X first |
