"""SQLite adapter for durable command-state foundation; no execution or cleanup."""
from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path
from agent.contracts.lifecycle import CommandLifecycle, CommandState, RequestedPriority

SCHEMA_VERSION=1
class DurableStateError(RuntimeError): pass
class DuplicateCommandError(DurableStateError): pass

class SQLiteDurableCommandState:
    def __init__(self,path: str|Path):
        self.path=str(path); self.connection=sqlite3.connect(self.path,timeout=5, isolation_level=None)
        self.connection.execute("PRAGMA foreign_keys=ON"); self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("PRAGMA journal_mode=WAL")
        version=self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0,SCHEMA_VERSION): raise DurableStateError("unsupported schema version")
        if version==0:
            with self.connection:
                self.connection.execute("CREATE TABLE commands (server_command_id TEXT PRIMARY KEY, command_identifier TEXT NOT NULL, command_version TEXT NOT NULL, received_at TEXT NOT NULL, expires_at TEXT, requested_priority TEXT NOT NULL, state TEXT NOT NULL, point_of_no_return INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
                self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    def close(self): self.connection.close()
    def insert(self,item:CommandLifecycle):
        now=item.received_at.isoformat()
        try:
            with self.connection: self.connection.execute("INSERT INTO commands VALUES (?,?,?,?,?,?,?,?,?,?)",(item.server_command_id,item.command_identifier,item.command_version,item.received_at.isoformat(),item.expires_at.isoformat() if item.expires_at else None,item.requested_priority.value,item.state.value,int(item.point_of_no_return),now,now))
        except sqlite3.IntegrityError as exc: raise DuplicateCommandError("duplicate server command identity") from exc
    def _item(self,row):
        if row is None:return None
        return CommandLifecycle(row[0],row[1],row[2],datetime.fromisoformat(row[3]),datetime.fromisoformat(row[4]) if row[4] else None,RequestedPriority(row[5]),CommandState(row[6]),bool(row[7]))
    def load(self,server_command_id): return self._item(self.connection.execute("SELECT server_command_id,command_identifier,command_version,received_at,expires_at,requested_priority,state,point_of_no_return FROM commands WHERE server_command_id=?",(server_command_id,)).fetchone())
    def transition(self,server_command_id,state):
        item=self.load(server_command_id)
        if item is None: raise KeyError(server_command_id)
        next_item=item.transition(state,datetime.now(item.received_at.tzinfo))
        with self.connection:self.connection.execute("UPDATE commands SET state=?,point_of_no_return=?,updated_at=? WHERE server_command_id=?",(next_item.state.value,int(next_item.point_of_no_return),datetime.now().astimezone().isoformat(),server_command_id))
        return next_item
    def recovery_candidates(self):
        rows=self.connection.execute("SELECT server_command_id,command_identifier,command_version,received_at,expires_at,requested_priority,state,point_of_no_return FROM commands WHERE state NOT IN ('succeeded','failed','expired','cancelled','ambiguous') ORDER BY received_at,server_command_id").fetchall()
        return tuple(self._item(row) for row in rows)
