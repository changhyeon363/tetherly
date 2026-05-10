---
icon: lucide/webhook
---

# Claude Code Hooks — Internals

Notes for contributors working on the `claude-stop` and `claude-notification` handlers. End-user setup and gating semantics live in [Architecture](../reference/architecture.md).

## What we hook

### `Stop`

Claude Code calls `Stop` when its turn ends. Payload includes:

- `hook_event_name` (`"Stop"`)
- `stop_hook_active` — `true` when Claude is already continuing because a previous Stop hook returned a block decision
- `last_assistant_message` (optional)
- common input fields (`session_id`, `transcript_path`, `cwd`, `permission_mode`, ...)

`tetherly claude-stop` reads the payload from stdin and forwards `last_assistant_message` to the bound chat. It **skips** when `stop_hook_active` is `true` to avoid double-firing if another hook is keeping Claude going. Always emits `{}` so it does not request a continuation.

### `Notification`

Claude Code calls `Notification` to surface non-tool events (idle prompts, permission prompts, auth events, etc.). Payload includes:

- `hook_event_name` (`"Notification"`)
- `notification_type` (e.g. `permission_prompt`, `idle_prompt`, `auth_success`)
- `message` — human-readable text (stripped of control characters, truncated to 1024 chars by Claude Code)
- common input fields

`tetherly claude-notification` forwards `[{notification_type}] {message}` to the bound chat. When `notification_type == "permission_prompt"` it uses `MessageIntent.PERMISSION` so the chat receives the Yes/No keyboard; everything else uses `MessageIntent.PLAIN`. Always emits `{}`.

## Design decisions worth remembering

### Why `Notification` instead of `PermissionRequest`

Claude Code does expose a separate `PermissionRequest` event with `tool_name` / `tool_input`. We chose `Notification` because:

- `Notification` is documented as non-blocking by design; no risk of accidentally returning a `deny`-shaped payload that interferes with the local prompt.
- `Notification` already carries a human-readable `message`, so we don't need to reconstruct a label from `tool_input`.
- It also covers `idle_prompt` and other non-permission cases — useful for users who want a ping when Claude is waiting on input.

If you ever need richer info (tool name, full input dict) the right move is to add a parallel `PermissionRequest` handler, not to convert the existing one.

### How to opt into auto-decisions later

Claude Code's `PermissionRequest` accepts a structured response:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": { "behavior": "allow", "updatedInput": { "...": "..." } }
  }
}
```

We deliberately don't emit that today. `Notification` does **not** support a decision field at all.

## Hook output rules (reference)

- `Stop` and `Notification` both honor the universal JSON-on-stdout-when-exit-0 contract. Use `{}` for "no opinion".
- Exit code `2` would block (for Stop) or be ignored (for Notification). We always exit 0.
- Informational logs from these handlers go to stderr, never stdout.

## Local logs

Each handler appends its raw payload to `<project>/.claude/logs/{stop,notification}.jsonl` for offline inspection. The directory is gitignored.

## Installer behavior

`tetherly init` and `tetherly install-claude-hooks` both call `setup.install_claude_hooks(scope=...)`. The user-facing merge rules — what's preserved, when backups are written, the malformed-JSON edge case — are documented in [Architecture: Hook installer](../reference/architecture.md#hook-installer-how-existing-files-are-merged).

Contributor notes on top of that:

- Unlike Codex, Claude Code has **no separate feature flag** — hooks in `settings.json` are active as soon as the file is parsed. So `install_claude_hooks` only writes one file (`settings.json`), and `ClaudeHookInstallResult` only carries one path/diff.
- The command embedded in `settings.json` is hard-coded to the bare string `"tetherly"` via `resolve_tetherly_executable()`. We rely on the user's `PATH` to resolve it; we do **not** record an absolute path. Same reasoning as the Codex installer: a recorded path would break across `pipx upgrade`.
- Idempotency is implemented by serializing the merged dict with `json.dumps(..., sort_keys=True)` before and after the merge and only writing if they differ. New event keys would need to participate in that comparison.
- The merge intentionally re-uses Codex's `_hook_entry` / `_merge_hook_event` / `_entry_uses_subcommand` helpers, because Claude Code's `hooks` array shape (`{"matcher": ..., "hooks": [{type, command, ...}]}`) matches Codex's.

The merge logic lives in [`src/tetherly/setup.py`](../../src/tetherly/setup.py).
