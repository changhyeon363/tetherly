---
icon: lucide/webhook
---

# Codex Hooks — Internals

Notes for contributors working on the `codex-stop` and `codex-permission-request` handlers. End-user setup and gating semantics live in [Architecture](../reference/architecture.md).

## What we hook

Both handlers replace the legacy `notify` integration that we removed.

### `Stop`

Codex calls `Stop` when a turn ends. Payload includes:

- `turn_id`
- `stop_hook_active`
- `last_assistant_message` (optional)
- common input fields (`cwd`, `hook_event_name`, ...)

`tetherly codex-stop` reads the JSON payload from stdin, looks up the bound chat (Discord or Telegram) for the active tmux session, and forwards `last_assistant_message`. It always emits `{}` on stdout so the hook does not request a continuation.

### `PermissionRequest`

Codex calls `PermissionRequest` before showing an approval prompt. Payload includes:

- `turn_id`
- `tool_name` (canonical: `Bash`, `apply_patch`, `mcp__server__tool`, ...)
- `tool_input`
- `tool_input.description` (optional human-readable reason)

The payload does **not** include the TUI option labels (`1. Yes, proceed`, `2. Yes, and don't ask again for commands that start with X`, etc.) — those are rendered locally by the Codex TUI from the raw command and never travel through the hook.

`tetherly codex-permission-request` forwards a chat message with `tool_name`, the command (for `Bash`/`apply_patch`) or the full `tool_input` (for MCP tools), and the reason. It emits `{}` — no `allow`/`deny` decision — so Codex's normal approval prompt still surfaces in the terminal.

## Design decisions worth remembering

### Why we don't capture tmux pane output for permission prompts

A tail-based variant (capture recent tmux pane output instead of parsing the payload) was tried and reverted: the hook fires before the TUI renders the approval prompt, so capture timing was unreliable even with a fixed sleep.

### How to opt into auto-decisions later

The handler can be extended to emit:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": { "behavior": "allow" }
  }
}
```

`deny` wins over `allow` if multiple matching hooks return decisions.

## Hook output rules (reference)

- `Stop` requires JSON on stdout when exit is 0 — plain text is invalid. Use `{}` for "no continuation".
- `PermissionRequest` ignores plain text on stdout. Returning `{}` (or no body) leaves the normal approval flow intact.
- Informational logs from these handlers go to stderr, never stdout.

## Local logs

Each handler appends its raw payload to `<project>/.codex/logs/{stop,permission-request}.jsonl` for offline inspection. The directory is gitignored.

## Installer behavior

`tetherly init` and `tetherly install-hooks` both call `setup.install_codex_hooks(scope=...)`. The user-facing merge rules — what's preserved, when backups are written, the malformed-JSON edge case — are documented in [Architecture: Hook installer](../reference/architecture.md#hook-installer-how-existing-files-are-merged).

Contributor notes on top of that:

- The command embedded in `hooks.json` is hard-coded to the bare string `"tetherly"` via `resolve_tetherly_executable()`. We rely on the user's `PATH` to resolve it; we do **not** record an absolute path. Keep this in mind if you ever change the install layout — pinning a path here would break for users who upgrade with `pipx upgrade` and end up at a different shim.
- Idempotency for `hooks.json` is implemented by serializing `data` with `json.dumps(..., sort_keys=True)` before and after the merge and only writing if they differ. New event keys would need to participate in that comparison.
- `config.toml` is rewritten with a minimal text-level edit (regex around the `[features]` section) rather than a TOML round-trip, to avoid reordering or reformatting the user's other tables.

The merge logic lives in [`src/tetherly/setup.py`](../../src/tetherly/setup.py).
