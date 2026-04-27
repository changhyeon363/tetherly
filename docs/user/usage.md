# tetherly — Usage Guide

This document explains the operating model and the parts that aren't obvious from a quick `--help`.

## 1. Architecture

tetherly is **one bot, many tmux sessions, many Discord channels**.

- A single bot process (one Discord token) runs on your machine.
- It maintains a state file mapping `Discord channel ↔ tmux session name`.
- tmux sessions are global to the machine; the bot bridges Discord traffic into whichever session is bound to the current channel.

There is no need to run a separate bot per project. Each project simply binds its own tmux session to its own Discord channel.

## 2. Setup

### One-time, machine-wide

```bash
pipx install tetherly
# or: uv tool install tetherly
tetherly init
```

`tetherly init` is interactive. It writes:

- `~/.tetherly/.env` — Discord token + allowed user/guild IDs (chmod 600).
- `~/.tetherly/state.json` — created on first bind, used for all bindings.

It then asks where to install Codex hooks:

| Choice | Writes | Effect |
| --- | --- | --- |
| **Global** | `~/.codex/hooks.json`, `~/.codex/config.toml` (once) | Hooks fire in every project automatically. Nothing else needed per project. |
| **Project** | nothing | Run `tetherly install-hooks` inside each project where you want hooks. |
| **Skip** | nothing | No Codex hooks at all. You can run `tetherly install-hooks` later. |

### Why "Global" is safe by default

Even when hooks are registered globally, **only sessions explicitly bound via `/bind` actually produce Discord notifications**. See [§4 Gating](#4-gating-why-global-hooks-stay-quiet-by-default).

### Re-running

- `tetherly init` again: backs up existing files to `*.bak`, prompts before overwriting.
- `tetherly install-hooks` (project) or `tetherly install-hooks --global`: idempotent. Existing entries for unrelated hook events (or other tools) are preserved — the installer appends our entry instead of replacing the array.

### Starting the bot

```bash
tetherly
```

State persists at `~/.tetherly/state.json`, so the bot survives restarts.

## 3. Per-project workflow

For each project you want to drive from Discord:

```bash
tmux new -s <session-name>
```

Then in the Discord channel you want to use:

```text
/bind session:<session-name>
/config auto_send:true   # optional, lets you skip /send
```

If you chose **Project** mode in step 2, also do once per project:

```bash
cd <project>
tetherly install-hooks
```

That's the entire per-project setup.

## 4. Gating: why global hooks stay quiet by default

The Codex `Stop` and `PermissionRequest` handlers only forward to Discord when **both** of the following are true:

1. The current shell is inside a tmux session (`TMUX_PANE` is set).
2. That session has `TETHERLY_NOTIFY_ON_FINISH=1` in its tmux session environment.

`/bind` is the only thing that sets the flag (via `tmux set-environment -t <session> TETHERLY_NOTIFY_ON_FINISH 1`). So:

| Situation | tmux session? | `NOTIFY_ON_FINISH=1`? | Outcome |
| --- | --- | --- | --- |
| Outside tmux (plain shell, cron, scripts) | ❌ | — | silent |
| Inside tmux, session not `/bind`-ed | ✅ | ❌ | silent |
| Inside `/bind`-ed session | ✅ | ✅ | message goes to the bound channel |

This is also why `tetherly init` defaults to global hook installation: there's no "noisy by default" failure mode.

### tmux env caveat

`tmux set-environment` updates the **session's environment**, not the OS-level environment of shells that are already running inside that session. After `/bind`, running `echo $TETHERLY_NOTIFY_ON_FINISH` in an existing shell may print nothing — that's normal. New windows/panes opened in the session inherit it. The hook handlers don't read the shell's env anyway: they query tmux directly with `tmux show-environment -t <session> TETHERLY_NOTIFY_ON_FINISH`.

## 5. Session detection for `discord-send`

`tetherly discord-send` (used by agents inside a bound tmux session) figures out which Discord channel to post to via this fallback chain ([`main.py:resolve_session_name`](../../src/tetherly/main.py)):

1. **`--session <name>` argument** — explicit override; always wins.
2. **`os.environ["TETHERLY_SESSION"]`** — useful when calling from outside tmux (cron, external scripts) where you exported the value yourself.
3. **`tmux display-message -p "#{session_name}"`** — uses the always-present `TMUX_PANE` env var that tmux injects at shell launch. **This works for any shell running inside tmux, regardless of when `/bind` happened**, because tmux itself answers the question.
4. **`tmux show-environment -t <session> TETHERLY_SESSION`** — final override using the session-level env that `/bind` wrote.

Practical consequence: layer 3 catches the common case automatically, so layer 2 being empty (because the shell pre-dates `/bind`) doesn't matter.

## 6. Command behavior worth knowing

### `/bind session:<name>`

Bindings live in `~/.tetherly/state.json`, keyed by **Discord channel ID**.

| Re-bind scenario | Result |
| --- | --- |
| Same channel + same session name | Silently overwrites. **`auto_send` resets to `false`**. `bound_at`/`last_used_at` reset. |
| Same channel + different session name | Silently overwrites. Old binding is dropped. The old tmux session is **not** killed. |
| Different channel + session name already bound elsewhere | Rejected: `"session 'foo' is already bound to channel X"`. There is currently no `/unbind` — fix by re-binding the old channel to a different session, or by editing `state.json`. |
| Different channel + new session name | Adds a new binding. |

Side note: `/bind` always calls `tmux_service.ensure_session(name)`, which **creates a fresh empty tmux session if the name doesn't exist**. A typo in the session name therefore silently creates an empty session — the response says `"Created and bound ..."` (vs `"Bound ..."`) which is the only signal.

### `/status`

Headline tells you whether the session is alive or gone:

```
🟢 Active — tmux session `t2` is alive
Channel: <#...>
Auto-send: `False`
Bound by: <@...>
Bound at: ...
Last used at: ...
```

```
🔴 tmux session `t2` is GONE — run `/bind session:<name>` to reconnect
Channel: <#...>
Auto-send: `False`
...
```

The 🔴 case happens when the binding still exists in `state.json` but the underlying tmux session was killed (e.g. machine reboot, `tmux kill-session`). To recover: just run `/bind` again — it will recreate the tmux session and refresh the binding.

### `/send`, `/key`, `/tail`

These respond with an ephemeral error if the tmux session is gone. **`auto_send` (plain text → tmux) does not** — failures only land in the bot's log. If your auto-sent messages disappear into the void, check `/status` first.

## 7. Files and paths

| Path | Role |
| --- | --- |
| `~/.tetherly/.env` | Discord token, allowed IDs. Loaded automatically. |
| `~/.tetherly/state.json` | Channel ↔ session bindings. |
| `~/.codex/config.toml` + `~/.codex/hooks.json` | Global hook install. Created by `tetherly init` (Global mode). |
| `<project>/.codex/config.toml` + `<project>/.codex/hooks.json` | Project-local hook install. Created by `tetherly install-hooks`. |
| `<project>/.codex/logs/*.jsonl` | Raw hook payloads, gitignored. |
| `./.env` | Optional per-shell override of values in `~/.tetherly/.env`. |

`TETHERLY_STATE_PATH` env var overrides the state file location if you ever need to.

## 8. Troubleshooting quick table

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `/status` shows 🔴 GONE | tmux session was killed, binding survived | `/bind session:<name>` again |
| `/bind` errors with `"already bound to channel X"` | Stale binding from another channel whose tmux is dead | Edit `state.json` to remove the old entry, or re-`/bind` from channel X |
| Plain-text auto-send seems silently ignored | tmux session is dead, or `auto_send=false` | `/status` to confirm; rebind or `/config auto_send:true` |
| Codex hooks never fire | Either hooks not installed (`tetherly install-hooks`), or current session not `/bind`-ed | Check `tmux show-environment -t <session> TETHERLY_NOTIFY_ON_FINISH` |
| `echo $TETHERLY_NOTIFY_ON_FINISH` empty inside a bound session | Expected — tmux set-environment doesn't reach existing shells | Hooks still work; ignore. |
