"""Controlled session-bound Worker launcher; never accepts remote executable input."""
from __future__ import annotations
import os, subprocess, sys, ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import win32con, win32process, win32ts
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
    def start_in_interactive_session(self,session_id:int):
        """Uses a Windows user token; target session is caller-selected, never Server input."""
        if self._process is not None and self._process.poll() is None: raise RuntimeError('WORKER_ALREADY_RUNNING')
        token=win32ts.WTSQueryUserToken(session_id)
        startup=win32process.STARTUPINFO(); command=f'"{sys.executable}" "{self._entry}"'
        _,_,pid,_=win32process.CreateProcessAsUser(token,None,command,None,None,False,win32con.CREATE_NO_WINDOW,None,str(self._entry.parent),startup)
        self._owned=OwnedWorker(pid,session_id,datetime.now(timezone.utc).isoformat(),str(self._entry)); return self._owned
    @staticmethod
    def active_interactive_session():
        current=[]
        for item in win32ts.WTSEnumerateSessions(None,1,0):
            session_id,_,state=item
            if session_id != 0 and state==win32ts.WTSActive: current.append(session_id)
        if len(current)!=1: raise RuntimeError('INTERACTIVE_SESSION_NOT_DETERMINISTIC')
        return current[0]
    def owned(self): return self._owned
    def stop(self):
        if self._process is None or self._process.poll() is not None: return False
        self._process.terminate(); self._process.wait(timeout=5); return True
