from datetime import datetime,timedelta,timezone
from agent.contracts.historical import HistoricalRequest, chunk_records
from agent.application.historical_transfer import HistoricalTransfer
from agent.infrastructure.sqlite_durable_state import SQLiteDurableCommandState

NOW=datetime(2026,1,1,tzinfo=timezone.utc)
def request(): return HistoricalRequest('t','EURUSD','rates',NOW,NOW+timedelta(hours=3),timedelta(hours=1),50)
def test_utc_partitions_and_bounded_deterministic_checksums():
    assert list(request().partitions())[-1][1] == request().end
    chunks=list(chunk_records('t',[{'time':'a','close':1},{'time':'b','close':2}],50))
    assert all(c.verify() for c in chunks) and chunks[-1].complete
def test_naive_or_invalid_range_or_type_is_rejected():
    import pytest
    with pytest.raises(ValueError): HistoricalRequest('t','X','rates',datetime(2026,1,1),NOW,timedelta(1),1)
    with pytest.raises(ValueError): HistoricalRequest('t','X','orders',NOW,NOW,timedelta(1),1)
class Reader:
    def read(self,*args): return iter([{'time':'2026-01-01T00:00:00+00:00','close':1}])
def test_checkpoint_resume_uses_outbox_and_survives_reopen(tmp_path):
    path=tmp_path/'s.db'; state=SQLiteDurableCommandState(path); transfer=HistoricalTransfer(state,Reader())
    assert transfer.run_partition(request(),0); assert state.history_checkpoint('t') == 0
    state.close(); state=SQLiteDurableCommandState(path); assert HistoricalTransfer(state,Reader()).run_partition(request(),0) == ()
    assert state.pending_outbox()[0]['topic'] == 'historical.chunk'
