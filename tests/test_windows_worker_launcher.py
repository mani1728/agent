import ctypes
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows launcher")

from agent.infrastructure.windows_worker_launcher import (
    ControlledWorkerLauncher,
    DiscoveredSession,
    WorkerSessionPolicy,
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
