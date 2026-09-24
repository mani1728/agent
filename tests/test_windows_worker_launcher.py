import ctypes
import os
import socket
import subprocess
from pathlib import Path

import pytest
import win32api
import win32security
import win32ts

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows launcher")

from agent.infrastructure.windows_worker_launcher import (
    ControlledWorkerLauncher,
    DiscoveredSession,
    WorkerSessionPolicy,
    interactive_startup_info,
    select_worker_session,
)


def test_launcher_tracks_owned_current_session_process_and_rejects_duplicate():
    launcher = ControlledWorkerLauncher(Path(__file__).parent / "fixtures" / "worker_sleeper.py")
    worker = launcher.start()
    try:
        current = ctypes.c_uint32()
        assert ctypes.windll.kernel32.ProcessIdToSessionId(
            os.getpid(), ctypes.byref(current)
        )
        assert worker.pid > 0
        assert worker.session_id == current.value
        with pytest.raises(RuntimeError, match="ALREADY"):
            launcher.start()
    finally:
        assert launcher.stop()


def test_session_selection_rejects_missing_or_wrong_local_principal_without_token_call():
    policy = WorkerSessionPolicy("MANI-PC\\Administrator")
    with pytest.raises(RuntimeError, match="SESSION_NOT_FOUND"):
        select_worker_session(policy, ())
    wrong_principal = DiscoveredSession(
        session_id=2,
        state="ACTIVE",
        session_name="Console",
        principal="MANI-PC\\OtherUser",
        is_session_zero=False,
        candidate=True,
        rejection_reason=None,
    )
    with pytest.raises(RuntimeError, match="SESSION_PRINCIPAL_MISMATCH"):
        select_worker_session(policy, (wrong_principal,))


def test_interactive_startup_targets_the_default_user_desktop():
    assert interactive_startup_info().lpDesktop == r"winsta0\default"


def _runner_service_identity() -> str:
    """Read the service account without changing Runner configuration."""
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance Win32_Service -Filter \"Name='gitlab-runner'\").StartName",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_authorized_window10_test_session_zero_prerequisites():
    """Fail closed before any future Window Station/Desktop ACL experiment."""
    assert socket.gethostname().casefold() == "window10-test"
    assert _runner_service_identity().casefold() == "localsystem"

    current_session = ctypes.c_uint32()
    assert ctypes.windll.kernel32.ProcessIdToSessionId(
        os.getpid(), ctypes.byref(current_session)
    )
    assert current_session.value == 0

    process = win32api.GetCurrentProcess()
    process_token = win32security.OpenProcessToken(process, win32security.TOKEN_QUERY)
    try:
        caller_sid = win32security.GetTokenInformation(
            process_token, win32security.TokenUser
        )[0]
        caller_name, caller_domain, _ = win32security.LookupAccountSid(None, caller_sid)
    finally:
        process_token.Close()
    assert f"{caller_domain}\\{caller_name}".casefold() == "nt authority\\system"

    policy = WorkerSessionPolicy.from_environment()
    assert policy.principal.casefold() == "window10-test\\administrator"
    selected = select_worker_session(policy, discover_sessions())
    assert selected.session_id != 0
    assert selected.state == "ACTIVE"

    target_token = win32ts.WTSQueryUserToken(selected.session_id)
    try:
        target_sid = win32security.GetTokenInformation(
            target_token, win32security.TokenUser
        )[0]
        target_name, target_domain, _ = win32security.LookupAccountSid(None, target_sid)
    finally:
        target_token.Close()
    assert f"{target_domain}\\{target_name}".casefold() == policy.principal.casefold()
    print(
        "ACL_PRECHECK passed "
        f"host=WINDOW10-TEST caller=LocalSystem session=0 "
        f"target_session={selected.session_id} target_principal={policy.principal} "
        "target_sid_resolved=true"
    )


def test_session_zero_can_launch_owned_worker_in_designated_interactive_session():
    current = ctypes.c_uint32()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(current))
    if current.value != 0:
        pytest.skip("cross-session evidence runs from service/session 0 only")
    policy = WorkerSessionPolicy.from_environment()
    launcher = ControlledWorkerLauncher(Path(__file__).parent / "fixtures" / "worker_sleeper.py")
    worker = launcher.start_for_local_policy(policy)
    try:
        observed = ctypes.c_uint32()
        assert ctypes.windll.kernel32.ProcessIdToSessionId(
            worker.pid, ctypes.byref(observed)
        )
        assert worker.session_id != 0
        assert observed.value == worker.session_id
        assert worker.pid > 0
        with pytest.raises(RuntimeError, match="ALREADY"):
            launcher.start_for_local_policy(policy)
    finally:
        assert launcher.stop()
