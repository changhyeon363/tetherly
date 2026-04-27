# Agent Discord Reply Guide

Use this project to send replies back to the Discord channel bound to the current tmux session.

## Default usage

When you are running inside a bound tmux session, send a Discord reply like this:

```bash
co-agent discord-send --message "<text>"
```

For longer output, send from standard input:

```bash
cat result.txt | co-agent discord-send --stdin
```

## When to use it

Use `discord-send` when you need to:

- report progress
- report completion
- ask the user a follow-up question
- return a concise result summary

## Session resolution

You usually do not need to pass a session name.

`co-agent discord-send` resolves the target session in this order:

1. `--session <name>` if explicitly provided
2. `CO_AGENT_SESSION` from the process environment
3. `CO_AGENT_SESSION` stored in the current tmux session
4. the current tmux session name as a fallback

That means the normal form inside tmux is:

```bash
co-agent discord-send --message "<text>"
```

If you must send from outside tmux, use:

```bash
co-agent discord-send --session <session> --message "<text>"
```

## Requirements

- The Discord channel must already be bound with:

```text
/bind session:<name>
```

- `~/.co-agent/.env` (or a CWD `.env` for an override) must contain a valid `DISCORD_BOT_TOKEN`. `co-agent init` writes this file for you.
- The bound session must be present in `~/.co-agent/state.json` (override with `CO_AGENT_STATE_PATH`).

## Failure checks

If sending fails:

1. In Discord, run `/status` in the target channel.
2. Confirm the channel is bound to the expected session.
3. If needed, run `/bind session:<name>` again in the current channel.
4. If running outside tmux, pass `--session <name>` explicitly.

## Examples

```bash
co-agent discord-send --message "작업이 끝났습니다."
```

```bash
printf "테스트 통과\n배포 준비 완료\n" | co-agent discord-send --stdin
```
