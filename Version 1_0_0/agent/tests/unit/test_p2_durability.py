from __future__ import annotations

import tempfile
import threading
import unittest

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope
from agent.core.command_executor import CommandExecutor
from agent.core.worker import AgentWorker
from agent.transport.base import ITransportClient
from agent.reliability.idempotency import (
    IdempotencyError,
    SQLiteIdempotencyStore,
    fingerprint_payload,
)
from agent.security.command_authorizer import CommandAuthorizer


class _NoopTransport(ITransportClient):
    def __init__(self, events, commands, response_plan=None):
        self.events = events
        self.commands = list(commands)
        self._response_plan = (
            list(response_plan)
            if response_plan is not None
            else None
        )
        self.acks = []
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def poll_commands(self, timeout_sec=1.0):
        if not self.commands:
            return []

        return [self.commands.pop(0)]

    def send_response(self, response):
        self.events.append("response")

        if self._response_plan is not None:
            if not self._response_plan:
                return True

            outcome = self._response_plan.pop(0)

            if isinstance(outcome, Exception):
                raise outcome

            return bool(outcome)

        return True

    def send_heartbeat(self, heartbeat):
        return True

    def ack_command(self, command_id):
        self.acks.append(command_id)
        self.events.append("ack")


class _NoopDispatcher:
    def __init__(self, events):
        self.events = events

    def dispatch(self, command):
        self.events.append("dispatch")
        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"ok": True},
        )


class _ReplayExecutor(CommandExecutor):
    def __init__(self, events, *, fail_once=False):
        super().__init__(
            dispatcher=_NoopDispatcher(events),
            authorizer=CommandAuthorizer(rules=(), default_allow=True),
        )
        self.events = events
        self.fail_once = fail_once
        self.calls = 0

    def execute(self, command):
        self.calls += 1
        self.events.append("execute")

        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("intentional execution failure")

        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"ok": True},
        )


class _BrokenIdempotencyStore:
    def begin(self, key, *, fingerprint=None):
        raise IdempotencyError("storage unavailable")

    def complete(self, key, *, result=None):
        raise IdempotencyError("storage unavailable")

    def fail(self, key, *, error=None, result=None):
        raise IdempotencyError("storage unavailable")

    def get(self, key):
        return None

    def remove(self, key):
        return False


def _create_command(
    command_id: str,
    method: str = "manage_connection",
) -> CommandEnvelope:
    return CommandEnvelope.from_dict(
        {
            "command_id": command_id,
            "target_class": "Mt5_Manager",
            "target_method": method,
        }
    )


class TestP2Durability(unittest.TestCase):
    def test_replay_from_persistent_idempotency_on_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = f"{temp_dir}/idempotency.db"

            events1 = []
            command = _create_command("durable-replay")

            store1 = SQLiteIdempotencyStore(db_path)
            try:
                transport1 = _NoopTransport(events1, [command])
                executor1 = _ReplayExecutor(events1)
                worker1 = AgentWorker(
                    executor1,
                    transport1,
                    idempotency_store=store1,
                )
                worker1.start()
                worker1.run_once()
                worker1.stop()
            finally:
                store1.close()

            record_reader = SQLiteIdempotencyStore(db_path)
            try:
                record = record_reader.get(command.command_id)
                self.assertIsNotNone(record)
                self.assertIsInstance(record.result, ResponseEnvelope)
            finally:
                record_reader.close()

            self.assertEqual(executor1.calls, 1)
            self.assertEqual(len(events1), 3)

            events2 = []
            store2 = SQLiteIdempotencyStore(db_path)
            try:
                transport2 = _NoopTransport(events2, [command])
                executor2 = _ReplayExecutor(events2)
                worker2 = AgentWorker(
                    executor2,
                    transport2,
                    idempotency_store=store2,
                    reliability_config={"delivery_retry": {"max_attempts": 1}},
                )
                worker2.start()
                worker2.run_once()
                worker2.stop()
            finally:
                store2.close()

            self.assertEqual(executor2.calls, 0)
            self.assertEqual(events2, ["response", "ack"])
            self.assertEqual(len(transport2.acks), 1)

    def test_stale_in_progress_record_is_recovered_on_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = f"{temp_dir}/idempotency.db"
            clock_state = {"now": 1_700_000_000.0}

            def clock():
                return clock_state["now"]

            command = _create_command("stale-in-progress")
            fingerprint = fingerprint_payload(command.to_dict())

            store = SQLiteIdempotencyStore(
                db_path,
                in_progress_ttl_seconds=5.0,
                clock=clock,
            )
            try:
                store.begin(
                    command.command_id,
                    fingerprint=fingerprint,
                )
            finally:
                store.close()

            clock_state["now"] += 10.0

            restart_store = SQLiteIdempotencyStore(
                db_path,
                in_progress_ttl_seconds=5.0,
                clock=clock,
            )
            try:
                outcome = restart_store.begin(
                    command.command_id,
                    fingerprint=fingerprint,
                )
            finally:
                restart_store.close()

            self.assertTrue(outcome.accepted)
            self.assertFalse(outcome.duplicate)

    def test_sqlite_locking_and_concurrency(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = f"{temp_dir}/idempotency.db"

            store_a = SQLiteIdempotencyStore(db_path)
            store_b = SQLiteIdempotencyStore(db_path)
            try:
                barrier = threading.Barrier(2, timeout=10.0)
                results = {}
                errors = {}
                fingerprint = fingerprint_payload({"volume": 1})

                def _contend(name, store):
                    try:
                        barrier.wait()
                        for index in range(10):
                            store.begin(f"cmd-{name}-{index}")
                        results[name] = store.begin(
                            "cmd-contested",
                            fingerprint=fingerprint,
                        )
                    except Exception as exc:
                        errors[name] = exc

                thread_a = threading.Thread(
                    target=_contend,
                    args=("a", store_a),
                    daemon=True,
                )
                thread_b = threading.Thread(
                    target=_contend,
                    args=("b", store_b),
                    daemon=True,
                )
                thread_a.start()
                thread_b.start()
                thread_a.join(timeout=15.0)
                thread_b.join(timeout=15.0)

                self.assertFalse(thread_a.is_alive(), "thread a deadlocked")
                self.assertFalse(thread_b.is_alive(), "thread b deadlocked")

                accepted_count = 0
                rejected_count = 0

                for name in ("a", "b"):
                    if name in results:
                        outcome = results[name]
                        if outcome.accepted:
                            accepted_count += 1
                        else:
                            self.assertTrue(outcome.duplicate)
                            self.assertIsNotNone(outcome.record)
                            rejected_count += 1
                    else:
                        self.assertIsInstance(
                            errors[name],
                            IdempotencyError,
                        )
                        rejected_count += 1

                self.assertEqual(accepted_count, 1)
                self.assertEqual(rejected_count, 1)

                self.assertEqual(store_a.size(), 21)

                contested = store_a.get("cmd-contested")
                self.assertIsNotNone(contested)
                self.assertEqual(contested.fingerprint, fingerprint)
            finally:
                store_a.close()
                store_b.close()

    def test_persistent_duplicate_publish_failure_keeps_command_unacked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = f"{temp_dir}/idempotency.db"

            command = _create_command("durable-delivery-failure")
            events1 = []
            store1 = SQLiteIdempotencyStore(db_path)
            try:
                transport1 = _NoopTransport(events1, [command])
                executor1 = _ReplayExecutor(events1)
                worker1 = AgentWorker(
                    executor1,
                    transport1,
                    idempotency_store=store1,
                )
                worker1.start()
                worker1.run_once()
                worker1.stop()
            finally:
                store1.close()

            store2 = SQLiteIdempotencyStore(db_path)
            try:
                events2 = []
                transport2 = _NoopTransport(
                    events2,
                    [command],
                    response_plan=[False],
                )
                executor2 = _ReplayExecutor(events2)
                worker2 = AgentWorker(
                    executor2,
                    transport2,
                    idempotency_store=store2,
                    reliability_config={"delivery_retry": {"max_attempts": 1}},
                )
                worker2.start()
                worker2.run_once()
                worker2.stop()
            finally:
                store2.close()

            self.assertEqual(executor2.calls, 0)
            self.assertEqual(events2, ["response"])
            self.assertEqual(len(transport2.acks), 0)

            record_reader = SQLiteIdempotencyStore(db_path)
            try:
                record = record_reader.get(command.command_id)
            finally:
                record_reader.close()

            self.assertIsNotNone(record)
            self.assertIsInstance(record.result, ResponseEnvelope)

    def test_db_readwrite_failure_keeps_processing_path_alive(self):
        events = []
        command = _create_command("storage-failure")
        executor = _ReplayExecutor(events)
        transport = _NoopTransport(
            events,
            [command],
            response_plan=[True],
        )

        worker = AgentWorker(
            executor,
            transport,
            idempotency_store=_BrokenIdempotencyStore(),
            close_idempotency_store=False,
        )
        worker.start()
        worker.run_once()
        worker.stop()

        self.assertEqual(executor.calls, 0)
        self.assertEqual(events, ["response"])
        self.assertEqual(len(transport.acks), 0)
