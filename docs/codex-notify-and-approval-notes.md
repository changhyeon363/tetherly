# Codex Notify And Approval Notes

## Goal

This project binds a Discord channel to a tmux session with `/bind`.

Wanted behavior:

- when a Codex turn finishes, send the final assistant message to Discord
- when Codex asks for approval, send an approval-needed message to Discord

## What Works Reliably

### `notify`

Codex officially supports `notify` as an external command hook.

What it does:

- runs an external program when the agent finishes a turn
- passes a JSON payload as the final argument

What it is good for:

- forwarding the last assistant message to Discord

What it is not good for:

- approval-requested events

Current payload fields confirmed from Codex source:

- `type`
- `thread-id`
- `turn-id`
- `cwd`
- `client` optional
- `input-messages`
- `last-assistant-message` optional

Practical conclusion:

- `notify` is the stable path for `agent-turn-complete`

## What Did Not Work Reliably

### `PermissionRequest` hook

Codex source contains a `PermissionRequest` hook path and JSON schema.
However, in local testing it did not fire for the approval UI we cared about.

Observed result:

- `notify` worked
- `PermissionRequest`-based Discord alert did not arrive
- this remained true even after enabling `codex_hooks` in project-local config

Likely explanation:

- the installed Codex build exposes hook-related code, but the approval flow in practice does not currently route through that hook in a usable way for this scenario
- `codex_hooks` is still under development, not a stable feature surface

Practical conclusion:

- do not rely on `PermissionRequest` for production approval alerts yet

### `Stop` hook

`Stop` exists in source and is useful for end-of-turn or continuation control.
It is not the same thing as `approval-requested`.

Practical conclusion:

- `Stop` should not be treated as a direct substitute for approval-requested alerts

## TUI Notifications

Codex TUI supports built-in notifications.

Relevant type names confirmed from source:

- `agent-turn-complete`
- `approval-requested`
- `plan-mode-prompt`

Important limitation:

- `tui.notifications` is for local terminal or desktop notifications
- it does not call an external webhook or script

Practical conclusion:

- useful for local popups
- not sufficient for Discord delivery

## Current Project Implementation

The current project has a working `notify` integration for turn completion.

Implemented pieces:

- `/bind` now stores `CO_AGENT_NOTIFY_ON_FINISH=1` in the tmux session
- `co-agent codex-notify <payload>` handles Codex `notify` payloads
- project-local `.codex/config.toml` points `notify` to the local virtualenv binary

Flow:

1. Discord `/bind session:<name>`
2. tmux session gets:
   - `CO_AGENT_SESSION=<session>`
   - `CO_AGENT_NOTIFY_ON_FINISH=1`
3. Codex finishes a turn
4. Codex runs `./.venv/bin/co-agent codex-notify <payload>`
5. `co-agent` sends `last-assistant-message` to the bound Discord channel

## Important Operational Detail

Using `co-agent` directly in Codex config was not sufficient because the command was not on `PATH` in the relevant shell environment.

Safer project-local configuration is:

```toml
notify = ["./.venv/bin/co-agent", "codex-notify"]
```

Likewise for hook commands, use the local virtualenv binary path rather than assuming `PATH`.

## Current Recommendation

For now:

- keep `notify` for final assistant messages
- do not depend on `PermissionRequest` for approval alerts

If approval alerts are still required, use an external watcher approach instead of unstable Codex hook behavior.

Most realistic fallback options:

- wrapper around `codex` execution
- tmux pane watcher
- Codex session log watcher

## Recommended Next Step

If approval-requested Discord alerts remain necessary, prefer a non-hook watcher approach.

Recommended priority:

1. wrapper around `codex`
2. tmux pane watcher
3. session JSONL watcher

Reason:

- they depend less on unstable internal hook plumbing
- they are easier to verify end-to-end
- they can later be packaged as part of a plugin or reusable library flow
