"""SQLite durable operational state. Transactions never span external calls."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from agent.contracts.lifecycle import CommandLifecycle, CommandState, RequestedPriority

SCHEMA_VERSION = 3
class DurableStateError(RuntimeError): pass
class DuplicateCommandError(DurableStateError): pass

class SQLiteDurableCommandState:
    def __init__(self, path: str | Path):
        self.path = str(path); self.connection = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys=ON"); self.connection.execute("PRAGMA busy_timeout=5000"); self.connection.execute("PRAGMA journal_mode=WAL")
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION: raise DurableStateError("unsupported schema version")
        if version == 0: self._create_v1(); version = 1
        if version == 1: self._migrate_v2(); version = 2
        if version == 2: self._migrate_v3()
    def _create_v1(self):
        with self.connection:
            self.connection.execute("CREATE TABLE commands (server_command_id TEXT PRIMARY KEY, command_identifier TEXT NOT NULL, command_version TEXT NOT NULL, received_at TEXT NOT NULL, expires_at TEXT, requested_priority TEXT NOT NULL, state TEXT NOT NULL, point_of_no_return INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            self.connection.execute("PRAGMA user_version=1")
    def _migrate_v2(self):
        with self.connection:
            for column in ("agent_execution_id TEXT", "mt5_request_id TEXT", "mt5_order_ticket TEXT", "mt5_position_ticket TEXT", "reconciliation_state TEXT"): self.connection.execute("ALTER TABLE commands ADD COLUMN " + column)
            self.connection.execute("CREATE UNIQUE INDEX commands_execution_identity ON commands(agent_execution_id) WHERE agent_execution_id IS NOT NULL")
            self.connection.execute("PRAGMA user_version=2")
    def _migrate_v3(self):
        with self.connection:
            self.connection.execute("CREATE TABLE outbox (message_id TEXT PRIMARY KEY, topic TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, sequence INTEGER NOT NULL, sent_at TEXT, acknowledged_at TEXT, UNIQUE(topic, sequence))")
            self.connection.execute("PRAGMA user_version=3")
    def close(self): self.connection.close()
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
    def insert(self, item):
        now=item.received_at.isoformat()
        try:
            with self.connection: self.connection.execute("INSERT INTO commands (server_command_id,command_identifier,command_version,received_at,expires_at,requested_priority,state,point_of_no_return,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(item.server_command_id,item.command_identifier,item.command_version,item.received_at.isoformat(),item.expires_at.isoformat() if item.expires_at else None,item.requested_priority.value,item.state.value,int(item.point_of_no_return),now,now))
        except sqlite3.IntegrityError as exc: raise DuplicateCommandError("duplicate server command identity") from exc
    def _item(self,row):
        return None if row is None else CommandLifecycle(row[0],row[1],row[2],datetime.fromisoformat(row[3]),datetime.fromisoformat(row[4]) if row[4] else None,RequestedPriority(row[5]),CommandState(row[6]),bool(row[7]))
    def load(self, key): return self._item(self.connection.execute("SELECT server_command_id,command_identifier,command_version,received_at,expires_at,requested_priority,state,point_of_no_return FROM commands WHERE server_command_id=?",(key,)).fetchone())
    def transition(self,key,state):
        item=self.load(key)
        if item is None: raise KeyError(key)
        nxt=item.transition(state,datetime.now(item.received_at.tzinfo))
        with self.connection:self.connection.execute("UPDATE commands SET state=?,point_of_no_return=?,updated_at=? WHERE server_command_id=?",(nxt.state.value,int(nxt.point_of_no_return),self._now(),key))
        return nxt
    def recovery_candidates(self):
        rows=self.connection.execute("SELECT server_command_id,command_identifier,command_version,received_at,expires_at,requested_priority,state,point_of_no_return FROM commands WHERE state NOT IN ('succeeded','failed','expired','cancelled','ambiguous') ORDER BY received_at,server_command_id").fetchall(); return tuple(self._item(r) for r in rows)
    def mark_point_of_no_return(self,key):
        item=self.load(key)
        if item is None: raise KeyError(key)
        marked=item.mark_point_of_no_return()
        with self.connection:self.connection.execute("UPDATE commands SET point_of_no_return=1,updated_at=? WHERE server_command_id=?",(self._now(),key))
        return marked
    def execution_identity(self,key):
        row=self.connection.execute("SELECT agent_execution_id FROM commands WHERE server_command_id=?",(key,)).fetchone()
        if row is None: raise KeyError(key)
        if not row[0]:
            with self.connection:self.connection.execute("UPDATE commands SET agent_execution_id=?,updated_at=? WHERE server_command_id=? AND agent_execution_id IS NULL",(str(uuid4()),self._now(),key))
        return self.connection.execute("SELECT agent_execution_id FROM commands WHERE server_command_id=?",(key,)).fetchone()[0]
    def correlate(self,key,*,mt5_request_id=None,order_ticket=None,position_ticket=None):
        self.execution_identity(key)
        with self.connection:self.connection.execute("UPDATE commands SET mt5_request_id=COALESCE(?,mt5_request_id),mt5_order_ticket=COALESCE(?,mt5_order_ticket),mt5_position_ticket=COALESCE(?,mt5_position_ticket),updated_at=? WHERE server_command_id=?",(mt5_request_id,order_ticket,position_ticket,self._now(),key))
    def mark_ambiguous_after_ponr(self,key):
        item=self.load(key)
        if item is None or item.state is not CommandState.RUNNING or not item.point_of_no_return: raise DurableStateError("ambiguous outcome requires running point-of-no-return command")
        with self.connection:self.connection.execute("UPDATE commands SET state='ambiguous',reconciliation_state='still_ambiguous',updated_at=? WHERE server_command_id=?",(self._now(),key))
    def reconcile(self,key,outcome):
        if outcome not in {"proven_executed","proven_not_executed","still_ambiguous"}: raise ValueError("invalid reconciliation outcome")
        state={"proven_executed":"succeeded","proven_not_executed":"failed","still_ambiguous":"ambiguous"}[outcome]
        with self.connection:self.connection.execute("UPDATE commands SET state=?,reconciliation_state=?,updated_at=? WHERE server_command_id=?",(state,outcome,self._now(),key))
    def correlation(self,key):
        row=self.connection.execute("SELECT agent_execution_id,mt5_request_id,mt5_order_ticket,mt5_position_ticket,reconciliation_state FROM commands WHERE server_command_id=?",(key,)).fetchone()
        if row is None: raise KeyError(key)
        return dict(zip(("agent_execution_id","mt5_request_id","mt5_order_ticket","mt5_position_ticket","reconciliation_state"),row))
    def enqueue_outbox(self,topic,payload,message_id=None):
        message_id=message_id or str(uuid4()); encoded=json.dumps(payload,sort_keys=True,separators=(",",":"))
        with self.connection:
            seq=self.connection.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM outbox WHERE topic=?",(topic,)).fetchone()[0]
            self.connection.execute("INSERT INTO outbox(message_id,topic,payload,created_at,sequence) VALUES (?,?,?,?,?)",(message_id,topic,encoded,self._now(),seq))
        return message_id
    def pending_outbox(self):
        return tuple({"message_id":r[0],"topic":r[1],"payload":json.loads(r[2]),"sequence":r[3],"sent_at":r[4]} for r in self.connection.execute("SELECT message_id,topic,payload,sequence,sent_at FROM outbox WHERE acknowledged_at IS NULL ORDER BY topic,sequence,message_id"))
    def mark_sent(self,key):
        with self.connection:self.connection.execute("UPDATE outbox SET sent_at=? WHERE message_id=?",(self._now(),key))
    def acknowledge(self,key):
        with self.connection:self.connection.execute("UPDATE outbox SET acknowledged_at=? WHERE message_id=?",(self._now(),key))
    def resync_snapshot(self,agent_id,boot_id,protocol_version,capabilities):
        return {"agent_id":agent_id,"boot_id":boot_id,"protocol_version":protocol_version,"capabilities":capabilities,"pending_outbox":self.pending_outbox(),"unfinished_commands":tuple(x.server_command_id for x in self.recovery_candidates()),"ambiguous_executions":tuple(r[0] for r in self.connection.execute("SELECT server_command_id FROM commands WHERE state='ambiguous' ORDER BY server_command_id"))}
