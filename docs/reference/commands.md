---
icon: lucide/terminal
---

# Command Reference

Every slash command tetherly accepts, on both platforms. The same command set works on Discord and Telegram — only the argument syntax differs.

## Syntax differences at a glance

| Concept | Discord | Telegram |
| --- | --- | --- |
| Bind | `/bind session:work` | `/bind work` |
| Toggle auto-send | `/config auto_send:true` | `/config on` (or `off`) |
| Send text | `/send hello` | `/send hello` |
| Send special key | `/key Enter` | `/key Enter` |

Discord uses **named options** (`session:`, `auto_send:`); Telegram uses positional arguments. Otherwise the commands are identical.

## Commands

### `/bind <session>`

Bind the current chat to a tmux session. If the session doesn't exist yet, tetherly creates an empty one — the response says `"Created and bound …"` (vs `"Bound …"`), which is your only signal that you typo'd the name.

A tmux session is **globally unique across platforms** — bound to one Discord channel **or** one Telegram chat, never both. Run `/unbind` first to move it.

| Re-bind scenario | Result |
| --- | --- |
| Same chat, same session | Silently overwrites. **`auto_send` resets to `false`**. |
| Same chat, different session | Silently overwrites. Old binding dropped; old tmux session is **not** killed. |
| Session already bound elsewhere (any platform) | Rejected with an error pointing at the other chat. |
| Different chat, new session | New binding is added. |

Bindings live in `~/.tetherly/state.json` keyed by `(platform, channel/chat ID)`.

### `/unbind`

Release the current chat's binding. Required before binding the same tmux session somewhere else.

### `/config` (auto-send toggle)

When auto-send is on, **plain text** typed into the chat is forwarded to the bound tmux session followed by Enter — you don't need `/send`.

- Discord: `/config auto_send:true` / `/config auto_send:false`
- Telegram: `/config on` / `/config off`

`/bind` resets auto-send to `false`, so re-binding silences the chat until you turn it on again.

### `/send <text>`

Send `<text>` to the bound tmux session, followed by Enter. Works regardless of `auto_send`. Errors ephemerally if the session is gone.

### `/key <name>`

Send a special key. Accepted names: `Enter`, `Escape`, `Ctrl-C`, `Ctrl-D`, `Tab`, `Up`, `Down`, `Left`, `Right`.

### Quick-key aliases (Telegram only)

`/enter` `/esc` `/ctrlc` `/ctrld` `/tab` — single-tap shortcuts, no arguments.

### `/tail [N]`

Show the last `N` lines (default 80) of the bound session's tmux pane. Errors ephemerally if the session is gone.

### `/status`

Show binding metadata and whether the underlying tmux session is alive.

```
🟢 Active — tmux session `work` is alive
…
```

```
🔴 tmux session `work` is GONE — run `/bind` to reconnect
…
```

The 🔴 case happens when the binding still exists in `state.json` but the tmux session was killed (reboot, `tmux kill-session`, …). To recover, just `/bind` again — it recreates the session and refreshes the binding.

### `/help`

Print the command list inline. The bot also registers commands with each platform on startup so they appear in autocomplete.

## Inline buttons

Most messages tetherly posts attach inline buttons so you rarely need to type slash commands:

| Trigger | Buttons |
| --- | --- |
| Codex Stop alert ("작업이 끝났습니다") | `[Enter] [Tail] [Stop]` |
| Codex PermissionRequest alert | `[Yes] [No] [Tail]` (Yes = Enter, No = Ctrl-C) |
| `/status` | `[Refresh] [Tail] [Enter] [Stop]` |
| `/tail` | `[Refresh] [Enter] [Stop]` |

`Refresh` edits the same message in place via `editMessageText`, so the chat doesn't pile up duplicate snapshots. `Stop` maps to `Ctrl-C`. There is no permanent reply keyboard — the input area stays clean.

## Telegram: filling in arguments via reply

Telegram's `/` autocomplete sends the command **immediately** when you tap it, so picking `/send` from the menu would normally arrive with no text. The bot replies with a one-line prompt (a [ForceReply](https://core.telegram.org/bots/api#forcereply) message) — your input area auto-opens as a reply, and whatever you type next becomes the argument:

```text
You:  /send                     ← tapped from the autocomplete menu
Bot:  Reply to this message with the text to send (will be followed by Enter).
You:  ls                        ← typed as the auto-opened reply
Bot:  Sent to `work`.
```

Same flow for `/bind`, `/config`, `/key` when picked from autocomplete. Slash commands you type fully (e.g. `/send hello`) skip the prompt step. `/tail`, `/status`, `/unbind`, `/help`, and the quick-key aliases never need an argument.

## Behaviors worth knowing

- **`/send`, `/key`, `/tail`** respond with an ephemeral error if the tmux session is gone.
- **Plain-text auto-send does not.** Failures only land in the bot's log. If your auto-sent messages disappear into the void, run `/status` first.
- **Access denials are silent on both platforms** — non-allowlisted users get no reply at all (one log line server-side). See [Security](../security.md).
