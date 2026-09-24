"""Support-safe liveness, readiness, heartbeat and cooperative quiesce model."""
from dataclasses import dataclass
from enum import Enum
from time import monotonic
class MaintenanceState(str,Enum): NORMAL='normal'; QUIESCING='quiescing'; QUIESCED='quiesced'; RESYNC='resync'
@dataclass(frozen=True)
class HealthSnapshot:
    live:bool; ready:bool; state:MaintenanceState; reasons:tuple[str,...]; uptime_seconds:int
class HealthController:
    def __init__(self,storage_ok=lambda:True,mt5_ok=lambda:True): self._storage_ok=storage_ok; self._mt5_ok=mt5_ok; self._started=monotonic(); self._state=MaintenanceState.NORMAL
    def quiesce(self): self._state=MaintenanceState.QUIESCING
    def safe_point(self):
        if self._state is MaintenanceState.QUIESCING:self._state=MaintenanceState.QUIESCED
    def resync(self):
        if self._state is not MaintenanceState.QUIESCED: raise ValueError('resync requires quiesced state')
        self._state=MaintenanceState.RESYNC
    def normal(self):
        if self._state is not MaintenanceState.RESYNC: raise ValueError('normal requires resync')
        self._state=MaintenanceState.NORMAL
    def snapshot(self):
        reasons=[]
        if not self._storage_ok(): reasons.append('storage_unavailable')
        if not self._mt5_ok(): reasons.append('mt5_unavailable')
        if self._state is not MaintenanceState.NORMAL: reasons.append('maintenance_'+self._state.value)
        return HealthSnapshot(True,not reasons,self._state,tuple(reasons),int(monotonic()-self._started))
    def heartbeat(self,agent_id,version):
        s=self.snapshot(); return {'agent_id':agent_id,'version':version,'live':s.live,'ready':s.ready,'maintenance_state':s.state.value,'reasons':list(s.reasons),'uptime_seconds':s.uptime_seconds}
