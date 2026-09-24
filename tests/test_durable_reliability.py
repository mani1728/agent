from datetime import datetime, timezone
import sqlite3
import pytest
from agent.contracts.lifecycle import CommandLifecycle, CommandState
from agent.infrastructure.sqlite_durable_state import SQLiteDurableCommandState, DuplicateCommandError

NOW=datetime(2026,9,24,tzinfo=timezone.utc)
def command(key="cmd"): return CommandLifecycle(key,"trade.future","1",NOW)
def running(store,key="cmd"):
    store.insert(command(key)); store.transition(key,CommandState.VALIDATED); store.transition(key,CommandState.QUEUED); store.transition(key,CommandState.RUNNING)

def test_duplicate_delivery_is_one_durable_execution_and_survives_reopen(tmp_path):
    p=tmp_path/'s.db'; s=SQLiteDurableCommandState(p); s.insert(command())
    identity=s.execution_identity('cmd')
    with pytest.raises(DuplicateCommandError): s.insert(command())
    assert s.execution_identity('cmd') == identity
    s.correlate('cmd',mt5_request_id='request',order_ticket='order',position_ticket='position'); s.close()
    s=SQLiteDurableCommandState(p); assert s.correlation('cmd') == {'agent_execution_id':identity,'mt5_request_id':'request','mt5_order_ticket':'order','mt5_position_ticket':'position','reconciliation_state':None}

def test_crash_after_ponr_is_ambiguous_and_never_recovery_candidate(tmp_path):
    s=SQLiteDurableCommandState(tmp_path/'s.db'); running(s); s.mark_point_of_no_return('cmd'); s.mark_ambiguous_after_ponr('cmd')
    assert s.load('cmd').state is CommandState.AMBIGUOUS
    assert s.recovery_candidates() == ()
    s.reconcile('cmd','proven_executed'); assert s.load('cmd').state is CommandState.SUCCEEDED
    s.reconcile('cmd','proven_not_executed'); assert s.load('cmd').state is CommandState.FAILED
    s.reconcile('cmd','still_ambiguous'); assert s.load('cmd').state is CommandState.AMBIGUOUS

def test_schema_v1_migrates_without_losing_command(tmp_path):
    p=tmp_path/'v1.db'; c=sqlite3.connect(p); c.execute('CREATE TABLE commands (server_command_id TEXT PRIMARY KEY, command_identifier TEXT NOT NULL, command_version TEXT NOT NULL, received_at TEXT NOT NULL, expires_at TEXT, requested_priority TEXT NOT NULL, state TEXT NOT NULL, point_of_no_return INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)'); c.execute("INSERT INTO commands VALUES ('old','read','1',?,?,?,?,?,?,?)",(NOW.isoformat(),None,'normal','received',0,NOW.isoformat(),NOW.isoformat())); c.execute('PRAGMA user_version=1'); c.commit(); c.close()
    s=SQLiteDurableCommandState(p); assert s.load('old').server_command_id == 'old'; assert s.connection.execute('PRAGMA user_version').fetchone()[0] == 3

def test_outbox_requires_ack_and_retransmits_across_restart(tmp_path):
    p=tmp_path/'s.db'; s=SQLiteDurableCommandState(p); first=s.enqueue_outbox('result',{'z':1},'m1'); s.enqueue_outbox('result',{'a':2},'m2')
    assert [m['message_id'] for m in s.pending_outbox()] == [first,'m2']; s.mark_sent(first); s.close()
    s=SQLiteDurableCommandState(p); assert s.pending_outbox()[0]['sent_at'] is not None; s.acknowledge(first); assert [m['message_id'] for m in s.pending_outbox()] == ['m2']

def test_resync_reports_only_persisted_obligations(tmp_path):
    s=SQLiteDurableCommandState(tmp_path/'s.db'); running(s); s.mark_point_of_no_return('cmd'); s.mark_ambiguous_after_ponr('cmd'); s.enqueue_outbox('ack',{'command':'cmd'},'a')
    snapshot=s.resync_snapshot('agent','boot','1',[]); assert snapshot['ambiguous_executions'] == ('cmd',) and snapshot['pending_outbox'][0]['message_id'] == 'a'
