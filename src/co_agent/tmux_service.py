from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


class TmuxError(RuntimeError):
    pass


SESSION_RE = re.compile(r"[^A-Za-z0-9._-]+")


def normalize_session_name(raw: str) -> str:
    candidate = SESSION_RE.sub("-", raw.strip()).strip("-")
    if not candidate:
        raise ValueError("session name must include at least one valid character")
    return candidate


@dataclass(frozen=True)
class SessionStatus:
    session_name: str
    exists: bool


class TmuxService:
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            ["tmux", *args],
            check=False,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise TmuxError(proc.stderr.strip() or proc.stdout.strip() or "tmux failed")
        return proc

    def session_exists(self, session_name: str) -> bool:
        proc = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            check=False,
            text=True,
            capture_output=True,
        )
        return proc.returncode == 0

    def ensure_session(self, session_name: str) -> bool:
        if self.session_exists(session_name):
            return False
        self._run("new-session", "-d", "-s", session_name)
        return True

    def set_session_environment(self, session_name: str, key: str, value: str) -> None:
        if not self.session_exists(session_name):
            raise TmuxError(f"session {session_name!r} does not exist")
        self._run("set-environment", "-t", session_name, key, value)

    def get_session_environment(self, session_name: str, key: str) -> str | None:
        if not self.session_exists(session_name):
            raise TmuxError(f"session {session_name!r} does not exist")
        proc = subprocess.run(
            ["tmux", "show-environment", "-t", session_name, key],
            check=False,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            return None
        output = proc.stdout.strip()
        prefix = f"{key}="
        if output.startswith(prefix):
            return output[len(prefix) :]
        return None

    def get_current_session_name(self) -> str | None:
        if not (os.environ.get("TMUX") or os.environ.get("TMUX_PANE")):
            return None
        args = ["display-message", "-p"]
        pane = os.environ.get("TMUX_PANE")
        if pane:
            args.extend(["-t", pane])
        args.append("#{session_name}")
        proc = subprocess.run(
            ["tmux", *args],
            check=False,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            return None
        session_name = proc.stdout.strip()
        return session_name or None

    def send_text(self, session_name: str, text: str, *, press_enter: bool = True) -> None:
        if not self.session_exists(session_name):
            raise TmuxError(f"session {session_name!r} does not exist")
        self._run("send-keys", "-t", session_name, text)
        if press_enter:
            self._run("send-keys", "-t", session_name, "Enter")

    def capture_tail(self, session_name: str, lines: int) -> str:
        if not self.session_exists(session_name):
            raise TmuxError(f"session {session_name!r} does not exist")
        start = f"-{lines}"
        proc = self._run("capture-pane", "-p", "-S", start, "-t", session_name)
        return proc.stdout.rstrip()

    def get_status(self, session_name: str) -> SessionStatus:
        return SessionStatus(session_name=session_name, exists=self.session_exists(session_name))
