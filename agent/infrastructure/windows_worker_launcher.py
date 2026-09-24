"""Controlled, policy-bound Windows Worker launcher.

The control plane supplies only locally configured policy. It never accepts a
session id, executable, or command line from the Server.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import win32con
import win32event
import win32process
import win32ts


@dataclass(frozen=True)
class OwnedWorker:
    pid: int
    session_id: int
    started_at: str
    entry_point: str


@dataclass(frozen=True)
class WorkerSessionPolicy:
    """Locally configured, designated Worker principal."""

    principal: str

    @classmethod
    def from_environment(cls) -> "WorkerSessionPolicy":
        principal = os.environ.get("MT5_AGENT_WORKER_PRINCIPAL", "").strip()
        if not principal:
            raise RuntimeError("WORKER_SESSION_POLICY_NOT_CONFIGURED")
        return cls(principal=principal)


@dataclass(frozen=True)
class DiscoveredSession:
    session_id: int
    state: str
    session_name: str
    principal: str | None
    is_session_zero: bool
    candidate: bool
    rejection_reason: str | None

    def evidence(self) -> dict[str, object]:
        return asdict(self)


_WTS_STATES = {
    win32ts.WTSActive: "ACTIVE",
    win32ts.WTSConnected: "CONNECTED",
    win32ts.WTSConnectQuery: "CONNECT_QUERY",
    win32ts.WTSShadow: "SHADOW",
    win32ts.WTSDisconnected: "DISCONNECTED",
    win32ts.WTSIdle: "IDLE",
    win32ts.WTSListen: "LISTEN",
    win32ts.WTSReset: "RESET",
    win32ts.WTSDown: "DOWN",
    win32ts.WTSInit: "INIT",
}


def _session_principal(session_id: int) -> str | None:
    """Return account identity only; never expose tokens or credentials."""
    try:
        username = win32ts.WTSQuerySessionInformation(
            None, session_id, win32ts.WTSUserName
        ).strip()
        domain = win32ts.WTSQuerySessionInformation(
            None, session_id, win32ts.WTSDomainName
        ).strip()
    except Exception:
        return None
    if not username:
        return None
    return f"{domain}\\{username}" if domain else username


def discover_sessions() -> tuple[DiscoveredSession, ...]:
    """Describe all WTS sessions visible to the local control plane."""
    sessions: list[DiscoveredSession] = []
    for item in win32ts.WTSEnumerateSessions(None, 1, 0):
        session_id = int(item["SessionId"])
        state = int(item["State"])
        is_session_zero = session_id == 0
        if is_session_zero:
            reason = "SESSION_ZERO"
        elif state != win32ts.WTSActive:
            reason = "SESSION_NOT_ACTIVE"
        else:
            reason = None
        sessions.append(
            DiscoveredSession(
                session_id=session_id,
                state=_WTS_STATES.get(state, f"UNKNOWN_{state}"),
                session_name=str(item.get("WinStationName", "")),
                principal=_session_principal(session_id),
                is_session_zero=is_session_zero,
                candidate=reason is None,
                rejection_reason=reason,
            )
        )
    return tuple(sessions)


def session_inventory_evidence(
    sessions: tuple[DiscoveredSession, ...],
) -> list[dict[str, object]]:
    return [session.evidence() for session in sessions]


def select_worker_session(
    policy: WorkerSessionPolicy, sessions: tuple[DiscoveredSession, ...]
) -> DiscoveredSession:
    """Select exactly one active session for the locally designated principal."""
    active = [session for session in sessions if session.candidate]
    matching = [
        session
        for session in active
        if session.principal and session.principal.casefold() == policy.principal.casefold()
    ]
    if not active:
        raise RuntimeError("SESSION_NOT_FOUND")
    if not matching:
        raise RuntimeError("SESSION_PRINCIPAL_MISMATCH")
    if len(matching) != 1:
        raise RuntimeError("SESSION_AMBIGUOUS")
    return matching[0]


def interactive_startup_info() -> win32process.STARTUPINFO:
    """Target the selected user's existing interactive desktop.

    The launcher itself runs as a non-interactive LocalSystem service in
    session 0.  A null ``lpDesktop`` would inherit that service desktop rather
    than the desktop attached to the selected user's token.
    """
    startup = win32process.STARTUPINFO()
    startup.lpDesktop = r"winsta0\default"
    return startup


class ControlledWorkerLauncher:
    def __init__(self, worker_entry: Path):
        self._entry = worker_entry.resolve()
        self._process = None
        self._worker_handle = None
        self._owned: OwnedWorker | None = None

    def _worker_is_running(self) -> bool:
        return self._worker_handle is not None and (
            win32event.WaitForSingleObject(self._worker_handle, 0) == win32event.WAIT_TIMEOUT
        )

    def start(self) -> OwnedWorker:
        if (self._process is not None and self._process.poll() is None) or self._worker_is_running():
            raise RuntimeError("WORKER_ALREADY_RUNNING")
        self._process = subprocess.Popen(
            [sys.executable, str(self._entry)],
            cwd=str(self._entry.parent),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        value = ctypes.c_uint32()
        if not ctypes.windll.kernel32.ProcessIdToSessionId(
            self._process.pid, ctypes.byref(value)
        ):
            raise OSError("cannot determine worker session")
        self._owned = OwnedWorker(
            self._process.pid,
            value.value,
            datetime.now(timezone.utc).isoformat(),
            str(self._entry),
        )
        return self._owned

    def start_for_local_policy(self, policy: WorkerSessionPolicy) -> OwnedWorker:
        sessions = discover_sessions()
        try:
            selected = select_worker_session(policy, sessions)
        except RuntimeError as error:
            raise RuntimeError(
                f"{error.args[0]} inventory={session_inventory_evidence(sessions)!r}"
            ) from None
        return self._start_in_selected_session(selected)

    def _start_in_selected_session(self, selected: DiscoveredSession) -> OwnedWorker:
        if (self._process is not None and self._process.poll() is None) or self._worker_is_running():
            raise RuntimeError("WORKER_ALREADY_RUNNING")
        try:
            token = win32ts.WTSQueryUserToken(selected.session_id)
        except Exception as error:
            code = getattr(error, "winerror", None)
            raise RuntimeError(f"SESSION_TOKEN_UNAVAILABLE:{code!s}") from None
        startup = interactive_startup_info()
        command = f'"{sys.executable}" "{self._entry}"'
        try:
            try:
                process_handle, thread_handle, pid, _ = win32process.CreateProcessAsUser(
                    token,
                    None,
                    command,
                    None,
                    None,
                    False,
                    win32con.CREATE_NO_WINDOW,
                    None,
                    str(self._entry.parent),
                    startup,
                )
            finally:
                # WTSQueryUserToken returns an owned handle; the child has its
                # own token reference after CreateProcessAsUser returns.
                token.Close()
        except Exception as error:
            code = getattr(error, "winerror", None)
            raise RuntimeError(f"WORKER_CREATE_PROCESS_FAILED:{code!s}") from None
        thread_handle.Close()
        self._worker_handle = process_handle
        self._owned = OwnedWorker(
            pid,
            selected.session_id,
            datetime.now(timezone.utc).isoformat(),
            str(self._entry),
        )
        return self._owned

    def owned(self) -> OwnedWorker | None:
        return self._owned

    def stop(self) -> bool:
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=5)
            return True
        if self._worker_handle is not None:
            win32process.TerminateProcess(self._worker_handle, 0)
            win32event.WaitForSingleObject(self._worker_handle, 5000)
            self._worker_handle = None
            return True
        return False
