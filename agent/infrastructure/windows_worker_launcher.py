"""Controlled session-bound Worker launcher; never accepts remote executable input."""
from __future__ import annotations
import os, subprocess, sys, ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
@dataclass(frozen=True)
class OwnedWorker:
    pid:int; session_id:int; started_at:str; entry_point:str
class ControlledWorkerLauncher:
    def __init__(self,worker_entry:Path):
        self._entry=worker_entry.resolve(); self._process=None; self._owned=None
    def start(self):
        if self._process is not None and self._process.poll() is None: raise RuntimeError('WORKER_ALREADY_RUNNING')
        self._process=subprocess.Popen([sys.executable,str(self._entry)],cwd=str(self._entry.parent),creationflags=subprocess.CREATE_NO_WINDOW)
        value=ctypes.c_uint32()
        if not ctypes.windll.kernel32.ProcessIdToSessionId(self._process.pid,ctypes.byref(value)): raise OSError('cannot determine worker session')
        session=value.value
        self._owned=OwnedWorker(self._process.pid,session,datetime.now(timezone.utc).isoformat(),str(self._entry)); return self._owned
    def owned(self): return self._owned
    def stop(self):
        if self._process is None or self._process.poll() is not None: return False
        self._process.terminate(); self._process.wait(timeout=5); return True
