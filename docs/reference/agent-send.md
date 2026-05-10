---
icon: lucide/message-square-reply
---

# Agent Send (`tetherly send`)

Send replies back to the chat (Discord or Telegram) bound to the current tmux session. Used by Codex, Claude Code, and any other agent running inside a bound session.

## Usage

```bash
tetherly send --message "<text>"
```

For longer output, send from standard input:

```bash
cat result.txt | tetherly send --stdin
```

`tetherly send` automatically routes to whichever platform (Discord or Telegram) the session is bound to. The legacy `tetherly discord-send` is still accepted as an alias.

## When to use it

- report progress
- report completion
- ask the user a follow-up question
- return a concise result summary

## Session detection

You usually do not need to pass `--session`. Inside a bound tmux session, tetherly figures out the target chat automatically — see [Architecture → Session resolution](architecture.md#session-resolution-for-tetherly-send) for the full fallback chain.

If you must send from **outside tmux** (cron, external scripts), pass it explicitly:

```bash
tetherly send --session <session> --message "<text>"
```

## Requirements

- The chat must already be bound (`/bind <session>` on either platform).
- `~/.tetherly/.env` must contain a valid token for the platform the session is bound to (`DISCORD_BOT_TOKEN` or `TELEGRAM_BOT_TOKEN`). `tetherly init` writes this for you.
- The bound session must be present in `~/.tetherly/state.json` (override path with `TETHERLY_STATE_PATH`).

## When sending fails

1. In the bound chat, run `/status`.
2. Confirm the chat is bound to the expected session.
3. If the session is gone (🔴), `/bind` again.
4. If running outside tmux, pass `--session <name>` explicitly.

## Examples

```bash
tetherly send --message "작업이 끝났습니다."
```

```bash
printf "테스트 통과\n배포 준비 완료\n" | tetherly send --stdin
```
