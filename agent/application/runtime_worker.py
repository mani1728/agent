"""Versioned allowlisted runtime-worker boundary; transport-agnostic and fail closed."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from hmac import compare_digest
from uuid import uuid4
class WorkerState(str,Enum): NOT_PRESENT='not_present'; STARTING='starting'; READY='ready'; DEGRADED='degraded'; STOPPED='stopped'; FAILED='failed'
@dataclass(frozen=True)
class WorkerIdentity:
    instance_id:str; pid:int; session_id:int; account:str; started_at:str; protocol_version:str='1'
class RuntimeWorkerProtocol:
    """Only health and controlled shutdown are accepted; MT5 command dispatch stays allowlisted upstream."""
    def __init__(self,token,identity:WorkerIdentity): self._token=token; self.identity=identity; self.state=WorkerState.STARTING; self._seen=set()
    def handle(self,envelope):
        if not isinstance(envelope,dict) or not compare_digest(str(envelope.get('token','')),self._token): return {'ok':False,'code':'IPC_AUTHENTICATION_FAILED'}
        if envelope.get('version')!='1': return {'ok':False,'code':'IPC_UNSUPPORTED_VERSION'}
        request_id=envelope.get('request_id')
        if not isinstance(request_id,str) or request_id in self._seen:return {'ok':False,'code':'IPC_DUPLICATE_OR_INVALID_REQUEST'}
        self._seen.add(request_id); operation=envelope.get('operation')
        if operation=='handshake': self.state=WorkerState.READY; return {'ok':True,'identity':self.identity,'state':self.state.value}
        if operation=='health': return {'ok':True,'state':self.state.value}
        if operation=='shutdown': self.state=WorkerState.STOPPED; return {'ok':True,'state':self.state.value}
        return {'ok':False,'code':'IPC_UNSUPPORTED_OPERATION'}
class SingleWorkerLease:
    def __init__(self): self._identity=None
    def acquire(self,identity):
        if self._identity is not None: raise RuntimeError('WORKER_ALREADY_LEASED')
        self._identity=identity
    def release(self,identity):
        if self._identity != identity: raise RuntimeError('WORKER_OWNERSHIP_MISMATCH')
        self._identity=None
