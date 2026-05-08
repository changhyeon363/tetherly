---
icon: lucide/box
---

# Architecture

How the moving parts fit together: the bot process, tmux sessions, bindings, and the gating that keeps Codex hooks quiet by default.

## One process, many sessions, many chats

tetherly is **one bot process, optional Discord and Telegram bots, many tmux sessions, many chats**.

- A single bot process runs on your machine. It starts whichever bots you've configured (Discord, Telegram, or both) and shares state between them.
- It maintains a state file at `~/.tetherly/state.json` mapping `(platform, channel/chat ID) ↔ tmux session name`.
- A tmux session is **globally unique across platforms** — bound to one Discord channel **or** one Telegram chat, never both. To move it, `/unbind` from the current chat first.
- tmux sessions are global to the machine; the bot bridges chat traffic into whichever session is bound to the current chat.

You don't run a separate bot per project. Each project just binds its own tmux session to its own chat.

## Codex hook gating: why global hooks stay quiet

The Codex `Stop` and `PermissionRequest` handlers only forward to chat when **both** of the following are true:

1. The current shell is inside a tmux session (`TMUX_PANE` is set).
2. That session has `TETHERLY_NOTIFY_ON_FINISH=1` in its tmux session environment.

`/bind` is the only thing that sets the flag (via `tmux set-environment -t <session> TETHERLY_NOTIFY_ON_FINISH 1`). So:

| Situation | tmux session? | `NOTIFY_ON_FINISH=1`? | Outcome |
| --- | --- | --- | --- |
| Outside tmux (plain shell, cron, scripts) | ❌ | — | silent |
| Inside tmux, session not `/bind`-ed | ✅ | ❌ | silent |
| Inside `/bind`-ed session | ✅ | ✅ | message goes to the bound chat |

This is also why `tetherly init` defaults to global hook installation: there is no "noisy by default" failure mode.

### tmux env caveat

`tmux set-environment` updates the **session's environment**, not the OS-level environment of shells already running inside that session. After `/bind`, running `echo $TETHERLY_NOTIFY_ON_FINISH` in an existing shell may print nothing — that's normal. New windows/panes opened in the session inherit it. The hook handlers don't read the shell's env anyway: they query tmux directly with `tmux show-environment -t <session> TETHERLY_NOTIFY_ON_FINISH`.

## Session resolution for `tetherly send`

`tetherly send` (used by agents inside a bound tmux session) figures out which chat to post to. It first resolves the tmux session name, then looks up the binding and routes to whichever platform the session is bound to.

The fallback chain ([`main.py:resolve_session_name`](../../src/tetherly/main.py)):

1. **`--session <name>` argument** — explicit override; always wins.
2. **`os.environ["TETHERLY_SESSION"]`** — useful when calling from outside tmux (cron, external scripts) where you exported the value yourself.
3. **`tmux display-message -p "#{session_name}"`** — uses the always-present `TMUX_PANE` env var that tmux injects at shell launch. **This works for any shell running inside tmux, regardless of when `/bind` happened**, because tmux itself answers the question.
4. **`tmux show-environment -t <session> TETHERLY_SESSION`** — final override using the session-level env that `/bind` wrote.

Practical consequence: layer 3 catches the common case automatically, so layer 2 being empty (because the shell pre-dates `/bind`) doesn't matter.

See [Agent send](agent-send.md) for the user-facing CLI.

## Hook installer: how existing files are merged

`tetherly init` (Global mode) and `tetherly install-hooks` (Project mode) both write to two files inside `.codex/`: `config.toml` and `hooks.json` (under `~/.codex/` or `<project>/.codex/` depending on scope). Existing content in those files is preserved — the installer is **idempotent** and **non-destructive**.

### Idempotency and backups

- Re-running on an already-configured file produces no change and writes no backup.
- When a change is needed, the original is copied to `<file>.bak` in the same directory before the new content is written. The `.bak` is overwritten on each subsequent change.
- The CLI prints a unified diff (before → after) under the `✓` line whenever an existing file was modified, so you can see exactly what the installer touched. Newly-created files don't get a diff.

### `config.toml`

Only `[features].codex_hooks` is touched:

| Existing state | Action |
| --- | --- |
| `codex_hooks = true` already | No change. |
| `codex_hooks = false` | That line is flipped to `true`. |
| `[features]` exists, no `codex_hooks = true\|false` line | Fresh `codex_hooks = true` line inserted directly under `[features]`. |
| No `[features]` section | Section appended at end of file. |
| File doesn't exist | Created with just `[features]\ncodex_hooks = true`. |

Other tables and keys are left as-is.

### `hooks.json`

Only the `Stop` and `PermissionRequest` event arrays are modified, and even within those, only the entries matching tetherly's own subcommands are replaced:

- Top-level keys other than `hooks` — **preserved**.
- Event keys inside `hooks` other than `Stop` / `PermissionRequest` (e.g. `UserPromptSubmit`) — **preserved**.
- Within `Stop`: entries whose command contains `codex-stop` are removed; one fresh tetherly entry is appended. Entries running other tools' commands stay.
- Within `PermissionRequest`: same logic for `codex-permission-request`.

So if you already have hand-written hooks for the same events pointing at other commands, they coexist with tetherly's after the install.

**Edge case** — if the file exists but contains invalid JSON, or its top-level value isn't a JSON object, it's treated as `{}` and rewritten from scratch. The original content is preserved in `<file>.bak`, so you can restore by hand.

## Files and paths

| Path | Role |
| --- | --- |
| `~/.tetherly/.env` | Discord and/or Telegram tokens, allowed IDs. Loaded automatically. |
| `~/.tetherly/state.json` | `(platform, channel/chat) ↔ session` bindings. |
| `~/.codex/config.toml` + `~/.codex/hooks.json` | Global hook install. Created by `tetherly init` (Global mode). |
| `<project>/.codex/config.toml` + `<project>/.codex/hooks.json` | Project-local hook install. Created by `tetherly install-hooks`. |
| `<project>/.codex/logs/*.jsonl` | Raw hook payloads, gitignored. |
| `./.env` | Optional per-shell override of values in `~/.tetherly/.env`. |

`TETHERLY_STATE_PATH` env var overrides the state file location if you ever need to.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `/status` shows 🔴 GONE | tmux session was killed, binding survived | `/bind <name>` again |
| `/bind` errors with `"already bound to … channel X"` | Stale binding from another chat whose tmux is dead | `/unbind` in chat X (any platform), or edit `state.json` to remove the old entry |
| Plain-text auto-send seems silently ignored | tmux session is dead, or `auto_send=false` | `/status` to confirm; rebind or `/config` to enable auto-send |
| Codex hooks never fire | Hooks not installed, or current session not `/bind`-ed | Check `tmux show-environment -t <session> TETHERLY_NOTIFY_ON_FINISH` |
| `echo $TETHERLY_NOTIFY_ON_FINISH` empty inside a bound session | Expected — `tmux set-environment` doesn't reach existing shells | Hooks still work; ignore. |

Platform-specific troubleshooting lives with each platform page: [Discord](../platforms/discord.md), [Telegram](../platforms/telegram.md).
