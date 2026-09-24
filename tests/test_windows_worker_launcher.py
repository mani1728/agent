import os
from pathlib import Path
import pytest
import ctypes
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows launcher')
from agent.infrastructure.windows_worker_launcher import ControlledWorkerLauncher
def test_launcher_tracks_owned_current_session_process_and_rejects_duplicate():
 launcher=ControlledWorkerLauncher(Path(__file__).parent/'fixtures'/'worker_sleeper.py'); worker=launcher.start()
 try:
  current=ctypes.c_uint32(); assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(current)); assert worker.pid>0 and worker.session_id==current.value
  with pytest.raises(RuntimeError,match='ALREADY'): launcher.start()
 finally: assert launcher.stop()
def test_invalid_interactive_session_fails_closed():
 launcher=ControlledWorkerLauncher(Path(__file__).parent/'fixtures'/'worker_sleeper.py')
 with pytest.raises(Exception): launcher.start_in_interactive_session(999999)
def test_session_zero_can_launch_owned_worker_in_active_interactive_session():
 current=ctypes.c_uint32(); ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(current))
 if current.value != 0: pytest.skip('cross-session evidence runs from service/session 0 only')
 launcher=ControlledWorkerLauncher(Path(__file__).parent/'fixtures'/'worker_sleeper.py'); target=launcher.active_interactive_session(); worker=launcher.start_in_interactive_session(target)
 try: assert worker.session_id==target and worker.session_id != 0
 finally: assert launcher.stop()
