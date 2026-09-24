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
