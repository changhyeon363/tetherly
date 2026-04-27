# Codex Hook Notes

## Goal

This project binds a Discord channel to a tmux session with `/bind`.

Wanted behavior:

- when a Codex turn finishes, send the final assistant message to Discord
- when Codex asks for approval, send an approval-needed message to Discord

## Current Approach

Both behaviors are now driven by official Codex hooks. The legacy `notify` integration has been removed.

### `Stop` (replaces `notify`)

Codex calls the `Stop` hook when a turn ends. The payload includes:

- `turn_id`
- `stop_hook_active`
- `last_assistant_message` (optional)
- common input fields (cwd, hook_event_name, ...)

`co-agent codex-stop` reads the JSON payload from stdin, looks up the bound Discord channel for the active tmux session, and forwards `last_assistant_message`. It always emits `{}` on stdout so the hook does not request a continuation.

### `PermissionRequest`

Codex calls `PermissionRequest` before showing an approval prompt. The payload includes:

- `turn_id`
- `tool_name` (canonical: `Bash`, `apply_patch`, `mcp__server__tool`, ...)
- `tool_input`
- `tool_input.description` (optional human-readable reason)

The hook payload does **not** include the TUI option labels (`1. Yes, proceed`, `2. Yes, and don't ask again for commands that start with X`, etc.) — those are rendered locally by the Codex TUI from the raw command and never travel through the hook.

`co-agent codex-permission-request` reads the JSON from stdin and forwards a Discord message with `tool_name`, the command (for Bash/apply_patch) or full `tool_input` (for MCP tools), and the reason. It emits `{}` on stdout — no `allow` or `deny` decision is returned, so Codex's normal approval prompt still surfaces in the terminal.

A tail-based variant (capture the recent tmux pane output instead of parsing the payload) was tried and reverted: the hook fires before the TUI renders the approval prompt, so capture timing was unreliable even with a fixed sleep.

If we ever want to auto-approve or deny based on tool/repo policy, the handler can be extended to emit:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": { "behavior": "allow" }
  }
}
```

`deny` wins over `allow` if multiple matching hooks decide.

## Gating

Both handlers are gated by the tmux session environment variable `CO_AGENT_NOTIFY_ON_FINISH`. `/bind session:<name>` sets it to `1` so only sessions explicitly bound to a Discord channel produce alerts.

## Operational Detail

Codex resolves hook commands relative to its launch shell, so `co-agent` may not be on `PATH`. The project-local config uses the explicit virtualenv binary path:

```toml
# .codex/config.toml
[features]
codex_hooks = true
```

```json
// .codex/hooks.json
{
  "hooks": {
    "PermissionRequest": [
      { "hooks": [{ "type": "command", "command": "./.venv/bin/co-agent codex-permission-request" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "./.venv/bin/co-agent codex-stop" }] }
    ]
  }
}
```

## Hook Output Rules (reference)

- `Stop` requires JSON on stdout when exit is 0 — plain text is invalid. Use `{}` for "no continuation".
- `PermissionRequest` ignores plain text on stdout. Returning `{}` (or no body) leaves the normal approval flow intact.
- Informational logs from these handlers go to stderr, never stdout.

## Local Logs

Each handler appends its raw payload to `.codex/logs/{stop,permission-request}.jsonl` for offline inspection. The directory is gitignored.
