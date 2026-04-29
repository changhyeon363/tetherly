---
icon: lucide/message-square-reply
---

# Agent Reply Guide

Send replies back to the chat (Discord or Telegram) bound to the current tmux session.

## Default usage

When you are running inside a bound tmux session, send a reply like this:

```bash
tetherly send --message "<text>"
```

For longer output, send from standard input:

```bash
cat result.txt | tetherly send --stdin
```

`tetherly send` automatically routes to whichever platform (Discord or Telegram) the session is bound to. The legacy `tetherly discord-send` is still accepted as an alias.

## When to use it

Use `tetherly send` when you need to:

- report progress
- report completion
- ask the user a follow-up question
- return a concise result summary

## Session resolution

You usually do not need to pass a session name.

`tetherly send` resolves the target session in this order:

1. `--session <name>` if explicitly provided
2. `TETHERLY_SESSION` from the process environment
3. `TETHERLY_SESSION` stored in the current tmux session
4. the current tmux session name as a fallback

That means the normal form inside tmux is:

```bash
tetherly send --message "<text>"
```

If you must send from outside tmux, use:

```bash
tetherly send --session <session> --message "<text>"
```

## Requirements

- The chat must already be bound:

```text
# Discord
/bind session:<name>

# Telegram
/bind <name>
```

- `~/.tetherly/.env` (or a CWD `.env` for an override) must contain a valid token for the platform the session is bound to (`DISCORD_BOT_TOKEN` or `TELEGRAM_BOT_TOKEN`). `tetherly init` writes this file for you.
- The bound session must be present in `~/.tetherly/state.json` (override with `TETHERLY_STATE_PATH`).

## Failure checks

If sending fails:

1. In the bound chat, run `/status`.
2. Confirm the chat is bound to the expected session.
3. If needed, run `/bind` again in the current chat.
4. If running outside tmux, pass `--session <name>` explicitly.

## Examples

```bash
tetherly send --message "작업이 끝났습니다."
```

```bash
printf "테스트 통과\n배포 준비 완료\n" | tetherly send --stdin
```
