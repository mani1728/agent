import pytest
from agent.application.scheduler import BoundedScheduler,ScheduledWork
from agent.contracts.lifecycle import RequestedPriority as P
def test_urgent_precedes_bulk_and_fifo_breaks_ties():
 s=BoundedScheduler(); s.admit(ScheduledWork('bulk',P.BULK,0)); s.admit(ScheduledWork('urgent',P.CRITICAL,1)); s.admit(ScheduledWork('urgent2',P.CRITICAL,2)); assert [s.next().identity,s.next().identity]==['urgent','urgent2']
def test_bounded_admission_and_cancelled_work():
 s=BoundedScheduler(1); s.admit(ScheduledWork('x',P.LOW,0,cancelled=True)); assert s.next() is None
 with pytest.raises(RuntimeError,match='QUEUE_FULL'): s.admit(ScheduledWork('y',P.HIGH,1))
