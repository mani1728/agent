from datetime import datetime,timezone
import sqlite3
import pytest
from agent.contracts.lifecycle import CommandLifecycle,CommandState
from agent.infrastructure.sqlite_durable_state import SQLiteDurableCommandState,DuplicateCommandError,SCHEMA_VERSION
def item(i='one'):return CommandLifecycle(i,'agent.read','1',datetime(2026,9,24,tzinfo=timezone.utc))
def test_create_wal_duplicate_transition_recovery_and_reopen(tmp_path):
 p=tmp_path/'state.db'; store=SQLiteDurableCommandState(p); assert store.connection.execute('PRAGMA user_version').fetchone()[0]==SCHEMA_VERSION; assert store.connection.execute('PRAGMA journal_mode').fetchone()[0].lower()=='wal'
 store.insert(item());
 with pytest.raises(DuplicateCommandError):store.insert(item())
 assert store.transition('one',CommandState.VALIDATED).state is CommandState.VALIDATED
 assert [x.server_command_id for x in store.recovery_candidates()]==['one']; store.close()
 reopened=SQLiteDurableCommandState(p); assert reopened.load('one').state is CommandState.VALIDATED; reopened.close()
def test_unsupported_schema_fails_clearly(tmp_path):
 p=tmp_path/'bad.db'; con=sqlite3.connect(p); con.execute('PRAGMA user_version=99');con.close()
 with pytest.raises(RuntimeError,match='unsupported'):SQLiteDurableCommandState(p)
