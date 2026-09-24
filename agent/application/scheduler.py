"""Small deterministic cooperative scheduler; it never executes work itself."""
from dataclasses import dataclass
from agent.contracts.lifecycle import RequestedPriority
_BASE={RequestedPriority.CRITICAL:0,RequestedPriority.HIGH:1,RequestedPriority.NORMAL:2,RequestedPriority.LOW:3,RequestedPriority.BULK:4}
@dataclass(frozen=True)
class ScheduledWork:
    identity:str; requested:RequestedPriority; enqueued:int; cancelled:bool=False
class BoundedScheduler:
    def __init__(self,limit=100,aging_interval=10): self.limit=limit; self.aging_interval=aging_interval; self._items=[]; self._tick=0
    def admit(self,work):
        if len(self._items)>=self.limit: raise RuntimeError('QUEUE_FULL')
        self._items.append(work)
    def next(self):
        eligible=[w for w in self._items if not w.cancelled]
        if not eligible: return None
        def rank(w): return (max(0,_BASE[w.requested]-((self._tick-w.enqueued)//self.aging_interval)),w.enqueued,w.identity)
        chosen=min(eligible,key=rank); self._items.remove(chosen); self._tick+=1; return chosen
