from __future__ import annotations

import unittest
import sys
import types
import time
import threading

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope, ResponseStatus
from agent.security.command_authorizer import AuthorizationRule, CommandAuthorizer


# Kafka unit tests use deterministic fakes; no broker or credentials are used.
class _FakeKafkaMessage:
    def __init__(self, value, *, topic="cmd.test.p1", partition=0, offset=1, key=b"Mt5_Manager", headers=None):
        self._value = value
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._key = key
        self._headers = headers or []

    def value(self): return self._value
    def topic(self): return self._topic
    def partition(self): return self._partition
    def offset(self): return self._offset
    def key(self): return self._key
    def headers(self): return self._headers
    def error(self): return None


class _FakeKafkaError:
    _PARTITION_EOF = -191

    def __init__(self, code=1): self._code = code
    def code(self): return self._code


class _FakeKafkaException(Exception):
    pass


class _FakeConsumer:
    instances = []
    next_messages = []

    def __init__(self, config):
        self.config = dict(config)
        self.subscribed = []
        self.commits = []
        self.closed = False
        self.running = True
        self.__class__.instances.append(self)

    def subscribe(self, topics): self.subscribed = list(topics)
    def poll(self, timeout):
        if self.__class__.next_messages:
            return self.__class__.next_messages.pop(0)
        return None
    def commit(self, message=None, asynchronous=False):
        self.commits.append((message, asynchronous))
    def close(self): self.closed = True


class _FakeProducer:
    instances = []
    delivery_error = None
    delivery_on_produce = False
    delivery_on_flush = True

    def __init__(self, config):
        self.config = dict(config)
        self.produced = []
        self.closed = False
        self.__class__.instances.append(self)

    def produce(self, *, topic, key=None, value=None, headers=None, on_delivery=None):
        self.produced.append((topic, key, value, headers, on_delivery))
        if self.__class__.delivery_on_produce and on_delivery is not None:
            self._deliver(on_delivery)

    def _deliver(self, callback):
        class _Delivered:
            def topic(self): return "server.replies"
            def partition(self): return 0
            def offset(self): return 10
        callback(self.__class__.delivery_error, _Delivered())

    def poll(self, timeout): return None
    def flush(self):
        if self.__class__.delivery_on_flush:
            for _, _, _, _, callback in self.produced:
                if callback is not None:
                    self._deliver(callback)
            return 0
        return 1
    def close(self): self.closed = True


_kafka_stub = types.ModuleType("confluent_kafka")
_kafka_stub.Consumer = _FakeConsumer
_kafka_stub.Producer = _FakeProducer
_kafka_stub.KafkaError = _FakeKafkaError
_kafka_stub.KafkaException = _FakeKafkaException
sys.modules.setdefault("confluent_kafka", _kafka_stub)


class _FakeMt5Manager:
    def manage_connection(self, **kwargs):
        return {"ok": True, "method": "manage_connection"}

    def manage_symbols(self, **kwargs):
        return {"ok": True, "method": "manage_symbols"}

    def manage_market_book(self, **kwargs):
        return {"ok": True, "method": "manage_market_book"}

    def fetch_data(self, **kwargs):
        return {"ok": True, "method": "fetch_data"}

    def trade_manager(self, **kwargs):
        return {"ok": True, "method": "trade_manager"}

    def manage_positions_history(self, **kwargs):
        return {"ok": True, "method": "manage_positions_history"}


class _SpyDispatcher:
    def __init__(self) -> None:
        self.calls: list[CommandEnvelope] = []

    def dispatch(self, command: CommandEnvelope) -> ResponseEnvelope:
        self.calls.append(command)
        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"dispatched": True},
            metadata={"target_method": command.target_method},
        )


class TestCommandExecutorAuthorization(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Avoid importing legacy MT5 dependencies by injecting a small stub for
        # the adapter path before importing the core command_executor module.
        cls._patched_modules = []

        existing = sys.modules.pop("agent.core.meta_trader_manager", None)
        if existing is not None:
            cls._patched_modules.append(("agent.core.meta_trader_manager", existing))

        stub = types.ModuleType("agent.core.meta_trader_manager")
        stub.Mt5_Manager = _FakeMt5Manager
        sys.modules["agent.core.meta_trader_manager"] = stub

        from agent.core.command_executor import CommandExecutor
        from agent.core.dispatcher import Dispatcher

        cls.CommandExecutor = CommandExecutor
        cls.Dispatcher = Dispatcher

    @classmethod
    def tearDownClass(cls) -> None:
        sys.modules.pop("agent.core.meta_trader_manager", None)

        for name, module in cls._patched_modules:
            sys.modules[name] = module

    def test_authorizer_blocks_unauthorized_commands(self) -> None:
        executor = self.CommandExecutor(
            dispatcher=_SpyDispatcher(),
            authorizer=CommandAuthorizer(
                rules=(
                    AuthorizationRule(
                        target_class="Mt5_Manager",
                        methods=frozenset({"manage_connection"}),
                    ),
                ),
                default_allow=False,
            ),
        )

        allowed = CommandEnvelope.from_dict(
            {
                "target_class": "Mt5_Manager",
                "target_method": "manage_connection",
            }
        )
        unauthorized = CommandEnvelope.from_dict(
            {
                "target_class": "Mt5_Manager",
                "target_method": "trade_manager",
            }
        )

        allowed_response = executor.execute(allowed)
        self.assertEqual(allowed_response.status, ResponseStatus.OK)

        denied_response = executor.execute(unauthorized)
        self.assertEqual(
            denied_response.error_code,
            "COMMAND_UNAUTHORIZED",
        )

    def test_dispatcher_accepts_mt5_manager_argument(self) -> None:
        dispatcher = self.Dispatcher(mt5_manager=_FakeMt5Manager())

        command = CommandEnvelope.from_dict(
            {
                "target_class": "Mt5_Manager",
                "target_method": "manage_connection",
            }
        )

        response = dispatcher.dispatch(command)
        self.assertEqual(response.status, ResponseStatus.OK)
        self.assertEqual(response.data["method"], "manage_connection")




class _RecordingExecutor(__import__("agent.core.command_executor", fromlist=["CommandExecutor"]).CommandExecutor):
    def __init__(self, events, *, fail=False):
        from agent.core.command_executor import CommandExecutor
        super().__init__(
            dispatcher=_SpyDispatcher(),
            authorizer=CommandAuthorizer(rules=(), default_allow=True),
        )
        self.events = events
        self.fail = fail

    def execute(self, command):
        self.events.append("execute")
        if self.fail:
            raise RuntimeError("synthetic execution failure")
        response = ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"ok": True},
        )
        return response


class _PlanExecutor(__import__("agent.core.command_executor", fromlist=["CommandExecutor"]).CommandExecutor):
    def __init__(self, events, *, plan):
        from agent.core.command_executor import CommandExecutor
        super().__init__(
            dispatcher=_SpyDispatcher(),
            authorizer=CommandAuthorizer(rules=(), default_allow=True),
        )
        self.events = events
        self._plan = list(plan)

    def execute(self, command):
        self.events.append("execute")

        if self._plan:
            outcome = self._plan.pop(0)

            if isinstance(outcome, BaseException):
                raise outcome

            if isinstance(outcome, ResponseEnvelope):
                return outcome

        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"ok": True},
        )


class _SingleExecutionExecutor(__import__("agent.core.command_executor", fromlist=["CommandExecutor"]).CommandExecutor):
    def __init__(self, events):
        super().__init__(
            dispatcher=_SpyDispatcher(),
            authorizer=CommandAuthorizer(rules=(), default_allow=True),
        )
        self.events = events

    def execute(self, command):
        self.events.append("execute")
        if self.events.count("execute") > 1:
            raise RuntimeError("unexpected second execution")

        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"ok": True},
            metadata={"result": "single"},
        )


class _BlockingExecutor(__import__("agent.core.command_executor", fromlist=["CommandExecutor"]).CommandExecutor):
    def __init__(self, events, *, plan, start_event, release_event):
        super().__init__(
            dispatcher=_SpyDispatcher(),
            authorizer=CommandAuthorizer(rules=(), default_allow=True),
        )
        self.events = events
        self._plan = list(plan)
        self._start_event = start_event
        self._release_event = release_event
        self._started_once = False

    def execute(self, command):
        self.events.append("execute")

        if not self._started_once:
            self._start_event.set()
            self._started_once = True
            self._release_event.wait()

        if self._plan:
            outcome = self._plan.pop(0)

            if isinstance(outcome, BaseException):
                raise outcome

            if isinstance(outcome, ResponseEnvelope):
                return outcome

        return ResponseEnvelope.success(
            correlation_id=command.correlation_id,
            data={"ok": True},
        )


class _RecordingTransport(__import__("agent.transport.base", fromlist=["ITransportClient"]).ITransportClient):
    def __init__(self, events, commands, *, response_ok=True, response_plan=None):
        self.events = events
        self.commands = list(commands)
        self.response_ok = response_ok
        self._response_plan = list(response_plan) if response_plan is not None else None
        self.acks = []
        self.published_responses = []
        self.started = False
        self.stopped = False

    def start(self): self.started = True
    def stop(self): self.stopped = True
    def poll_commands(self, timeout_sec=1.0):
        if self.commands:
            return [self.commands.pop(0)]
        self._stop_after_poll = True
        return []
    def send_response(self, response):
        self.published_responses.append(response)
        self.events.append("response")

        if self._response_plan is not None:
            if not self._response_plan:
                return self.response_ok

            outcome = self._response_plan.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return bool(outcome)

        return self.response_ok
    def send_heartbeat(self, heartbeat): return True
    def ack_command(self, command_id):
        self.events.append("ack")
        self.acks.append(command_id)
        self.events.append("commit")


class TestP0WorkerFlow(unittest.TestCase):
    def _command(self, method="manage_connection", command_id=None):
        payload = {
            "target_class": "Mt5_Manager",
            "target_method": method,
        }
        if command_id is not None:
            payload["command_id"] = command_id

        return CommandEnvelope.from_dict(payload)

    def test_execute_response_ack_order(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command()
        worker = AgentWorker(_RecordingExecutor(events), _RecordingTransport(events, [command]))
        worker.start()
        worker.run_once()
        self.assertEqual(events, ["execute", "response", "ack", "commit"])

    def test_no_commit_before_response(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command()
        transport = _RecordingTransport(events, [command], response_ok=False)
        worker = AgentWorker(
            _RecordingExecutor(events),
            transport,
            reliability_config={
                "delivery_retry": {
                    "max_attempts": 1,
                }
            },
        )
        worker.start()
        worker.run_once()
        self.assertEqual(events, ["execute", "response"])
        self.assertEqual(transport.acks, [])

    def test_execute_idempotent_transient_retry(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command()
        transport = _RecordingTransport(events, [command])
        executor = _PlanExecutor(
            events,
            plan=(TimeoutError("temporary"), TimeoutError("temporary")),
        )
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {"max_attempts": 3},
                "command_retry_exceptions": (TimeoutError,),
            },
        )
        worker.start()
        worker.run_once()
        self.assertEqual(events.count("execute"), 3)
        self.assertEqual(events, ["execute", "execute", "execute", "response", "ack", "commit"])

    def test_execute_retry_limits(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command(command_id="retry-limit")
        transport = _RecordingTransport(events, [command])
        executor = _PlanExecutor(
            events,
            plan=(TimeoutError("temporary"), TimeoutError("temporary"), TimeoutError("temporary")),
        )
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {"max_attempts": 2},
                "command_retry_exceptions": (TimeoutError,),
            },
        )
        worker.start()
        worker.run_once()
        self.assertEqual(events.count("execute"), 2)
        self.assertEqual(transport.acks, [])
        self.assertIsNone(worker._idempotency_manager.get(command.command_id))

    def test_permanent_execution_error_is_not_retried(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command()
        transport = _RecordingTransport(events, [command])
        executor = _PlanExecutor(
            events,
            plan=(ValueError("permanent failure"),),
        )
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {"max_attempts": 4},
            },
        )
        worker.start()
        worker.run_once()
        self.assertEqual(events.count("execute"), 1)
        self.assertEqual(transport.acks, [])

    def test_backoff_stop_request_aborts_retry_wait(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command(command_id="retry-stop")
        transport = _RecordingTransport(events, [command])
        executor = _PlanExecutor(
            events,
            plan=(TimeoutError("temporary"), TimeoutError("temporary")),
        )
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {
                    "max_attempts": 3,
                    "base_delay_seconds": 10,
                    "max_delay_seconds": 20,
                },
                "command_retry_exceptions": (TimeoutError,),
            },
        )
        worker.start()

        thread = threading.Thread(target=worker.run_once)
        thread.start()

        time.sleep(0.05)
        worker.request_stop()

        thread.join(timeout=1.5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(events.count("execute"), 1)

    def test_duplicate_completed_command_replays_without_reexecution(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command(command_id="dup-replay")
        transport = _RecordingTransport(events, [command, command])
        executor = _SingleExecutionExecutor(events)
        worker = AgentWorker(
            executor,
            transport,
        )
        worker.start()
        worker.run_once()
        worker.run_once()
        self.assertEqual(events.count("execute"), 1)
        self.assertEqual(events, ["execute", "response", "ack", "commit", "response", "ack", "commit"])

    def test_duplicate_completed_command_publish_failure_for_replay_halts_ack(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command(command_id="dup-failed-delivery")
        transport = _RecordingTransport(
            events,
            [command, command],
            response_plan=(True, False),
        )
        executor = _SingleExecutionExecutor(events)
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "delivery_retry": {
                    "max_attempts": 1,
                },
            },
        )
        worker.start()
        worker.run_once()
        worker.run_once()
        self.assertEqual(events.count("execute"), 1)
        self.assertEqual(transport.acks, [command.command_id])

    def test_delivery_retry_attempts_and_commit_guard(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command()
        transport = _RecordingTransport(
            events,
            [command],
            response_plan=(False, False, True),
        )
        worker = AgentWorker(
            _RecordingExecutor(events),
            transport,
            reliability_config={
                "delivery_retry": {
                    "max_attempts": 3,
                    "base_delay_seconds": 0,
                },
            },
        )
        worker.start()
        worker.run_once()
        self.assertEqual(len([event for event in events if event == "response"]), 3)
        self.assertEqual(transport.acks, [command.command_id])

    def test_delivery_retry_is_bounded(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command(command_id="delivery-limit")
        transport = _RecordingTransport(
            events,
            [command],
            response_plan=(False, False, True),
        )
        worker = AgentWorker(
            _RecordingExecutor(events),
            transport,
            reliability_config={
                "delivery_retry": {
                    "max_attempts": 2,
                },
            },
        )
        worker.start()
        worker.run_once()
        self.assertEqual(len([event for event in events if event == "response"]), 2)
        self.assertEqual(transport.acks, [])

    def test_in_progress_duplicate_prevents_concurrent_execute(self):
        from agent.core.worker import AgentWorker
        events = []
        started = threading.Event()
        proceed = threading.Event()
        command = self._command(command_id="in-progress")
        executor = _BlockingExecutor(
            events,
            plan=(),
            start_event=started,
            release_event=proceed,
        )
        transport = _RecordingTransport(events, [command, command])
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {"max_attempts": 1},
            },
        )
        worker.start()

        thread1 = threading.Thread(
            target=worker._process_command,
            args=(command,),
        )
        thread2 = threading.Thread(
            target=worker._process_command,
            args=(command,),
        )

        thread1.start()
        self.assertTrue(started.wait(1.0))
        thread2.start()

        thread2.join(timeout=1.0)
        proceed.set()

        thread1.join(timeout=2.0)
        self.assertEqual(events.count("execute"), 1)
        self.assertEqual(len([event for event in events if event == "response"]), 2)
        self.assertIn(command.command_id, transport.acks)
    def test_delivery_retry_stopped_by_shutdown(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command()
        transport = _RecordingTransport(
            events,
            [command],
            response_plan=(False, False, False),
        )
        worker = AgentWorker(
            _RecordingExecutor(events),
            transport,
            reliability_config={
                "delivery_retry": {
                    "max_attempts": 3,
                },
            },
        )
        worker.start()
        worker.request_stop()
        worker.run_once()
        self.assertEqual(events.count("response"), 1)
        self.assertEqual(transport.acks, [])

    def test_execute_exception_does_not_ack_and_worker_can_continue(self):
        from agent.core.worker import AgentWorker
        events = []
        first = self._command("manage_connection")
        second = self._command("fetch_data")
        transport = _RecordingTransport(events, [first, second])
        worker = AgentWorker(_RecordingExecutor(events, fail=True), transport)
        worker.start()
        worker.run_once()
        worker.run_once()
        self.assertEqual(events, ["execute", "response", "execute", "response"])
        self.assertEqual(transport.acks, [])

    def test_command_failure_is_not_marked_as_completed(self):
        from agent.core.worker import AgentWorker
        events = []
        command = self._command(command_id="failed-not-complete")
        transport = _RecordingTransport(events, [command])
        executor = _PlanExecutor(
            events,
            plan=(RuntimeError("temporary"),),
        )
        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {
                    "max_attempts": 1,
                },
            },
        )
        worker.start()
        worker.run_once()
        self.assertIsNone(worker._idempotency_manager.get(command.command_id))

    def test_circuit_breaker_closed_open_half_open(self):
        from agent.core.worker import AgentWorker
        from agent.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        events = []
        command = self._command(command_id="breaker-test")
        transport = _RecordingTransport(events, [command, command, command])
        executor = _PlanExecutor(
            events,
            plan=(RuntimeError("temporary"), ResponseEnvelope.success(
                correlation_id=command.correlation_id,
                data={"ok": True},
            )),
        )

        clock = {"now": 0.0}

        breaker = CircuitBreaker(
            config=CircuitBreakerConfig(
                failure_threshold=1,
                recovery_timeout_seconds=5.0,
                success_threshold=1,
            ),
            clock=lambda: clock["now"],
        )

        worker = AgentWorker(
            executor,
            transport,
            reliability_config={
                "command_retry": {"max_attempts": 1},
            },
            circuit_breaker=breaker,
        )
        worker.start()

        worker.run_once()
        self.assertEqual(events.count("execute"), 1)
        self.assertTrue(breaker.is_open)

        worker.run_once()
        self.assertEqual(events.count("execute"), 1)

        clock["now"] += 10.0
        self.assertTrue(breaker.is_half_open)
        worker.run_once()
        self.assertEqual(events.count("execute"), 2)
        self.assertTrue(breaker.is_closed)


class TestP0KafkaSemantics(unittest.TestCase):
    def setUp(self):
        _FakeConsumer.instances.clear()
        _FakeConsumer.next_messages.clear()
        _FakeProducer.instances.clear()
        _FakeProducer.delivery_error = None
        _FakeProducer.delivery_on_produce = False
        _FakeProducer.delivery_on_flush = True

    def _config(self, **extra):
        config = {
            "kafka.enabled": True,
            "kafka.bootstrap_servers": ["test-broker:9092"],
            "kafka.group_id": "test-group",
            "kafka.topics.commands": ["cmd.test.p0", "cmd.test.p1", "cmd.test.p2"],
            "kafka.topics.replies": "server.replies",
            "kafka.enable_auto_commit": False,
            "kafka.commit_policy": "after_response",
        }
        config.update(extra)
        return config

    def test_listener_disables_auto_commit(self):
        from agent.transport.kafka.listener import KafkaListener
        listener = KafkaListener(self._config())
        self.assertFalse(listener._build_consumer_config()["enable.auto.commit"])

    def test_malformed_message_does_not_stop_listener(self):
        from agent.transport.kafka.listener import KafkaListener
        _FakeConsumer.next_messages.extend([
            _FakeKafkaMessage("not-valid-json-or-literal"),
            _FakeKafkaMessage(
                '{"target_class":"Mt5_Manager","target_method":"manage_connection"}',
                offset=2,
            ),
        ])
        listener = KafkaListener(self._config())
        self.assertEqual(listener.poll_commands(), [])
        commands = listener.poll_commands()
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].target_method, "manage_connection")

    def test_responder_delivery_success_is_confirmed(self):
        from agent.transport.kafka.responder import KafkaResponder
        producer = _FakeProducer({})
        responder = KafkaResponder(self._config())
        responder._ensure_producer = lambda: producer
        response = ResponseEnvelope.success(correlation_id="corr-test", data={"ok": True})
        self.assertTrue(responder.send_response(response))

    def test_responder_delivery_failure_is_not_success(self):
        from agent.transport.kafka.responder import KafkaResponder
        _FakeProducer.delivery_error = RuntimeError("delivery failed")
        producer = _FakeProducer({})
        responder = KafkaResponder(self._config())
        responder._ensure_producer = lambda: producer
        response = ResponseEnvelope.success(correlation_id="corr-test", data={"ok": True})
        self.assertFalse(responder.send_response(response))

    def test_transport_rejects_auto_commit(self):
        from agent.transport.kafka.kafka_transport import KafkaTransport
        with self.assertRaises(ValueError):
            KafkaTransport(self._config(**{"kafka.enable_auto_commit": True}))

    def test_transport_ack_is_not_double_committed(self):
        from agent.transport.kafka.kafka_transport import KafkaTransport
        message = _FakeKafkaMessage('{"target_class":"Mt5_Manager","target_method":"manage_connection"}')
        _FakeConsumer.next_messages.append(message)
        transport = KafkaTransport(self._config())
        transport.start()
        commands = transport.poll_commands()
        transport.ack_command(commands[0].command_id)
        transport.ack_command(commands[0].command_id)
        consumer = _FakeConsumer.instances[-1]
        self.assertEqual(len(consumer.commits), 1)

    def test_multi_child_record_commits_only_after_all_children_ack(self):
        from agent.transport.kafka.kafka_transport import KafkaTransport
        payload = '[{"target_class":"Mt5_Manager","target_method":"manage_connection"},{"target_class":"Mt5_Manager","target_method":"fetch_data"}]'
        _FakeConsumer.next_messages.append(_FakeKafkaMessage(payload))
        transport = KafkaTransport(self._config())
        transport.start()
        commands = transport.poll_commands()
        consumer = _FakeConsumer.instances[-1]
        transport.ack_command(commands[0].command_id)
        self.assertEqual(len(consumer.commits), 0)
        transport.ack_command(commands[1].command_id)
        self.assertEqual(len(consumer.commits), 1)

    def test_stop_closes_consumer_and_producer(self):
        from agent.transport.kafka.kafka_transport import KafkaTransport
        transport = KafkaTransport(self._config())
        producer = _FakeProducer({})
        transport.responder._ensure_producer = lambda: producer
        transport.start()
        transport.responder._producer = producer
        transport.stop()
        self.assertTrue(_FakeConsumer.instances[-1].closed)
        # KafkaResponder.close() flushes, closes when supported, and releases the reference.
        self.assertTrue(producer.closed)
        self.assertIsNone(transport.responder._producer)


class TestP0MainSelection(unittest.TestCase):
    def test_agent_worker_is_default_selection(self):
        from unittest.mock import patch
        import agent.main as main_module

        class _Config:
            def __init__(self):
                self._data = {
                    "kafka": {
                        "enabled": True,
                        "bootstrap_servers": ["test-broker:9092"],
                        "group_id": "test-group",
                        "topics": {"commands": ["cmd.test.p0"]},
                        "enable_auto_commit": False,
                        "commit_policy": "after_response",
                    },
                    "app": {},
                }

            def get(self, path, default=None):
                value = self._data
                for part in path.split("."):
                    if not isinstance(value, dict) or part not in value:
                        return default
                    value = value[part]
                return value

        class _Auth:
            client_id = "test-client"
            def __init__(self, **kwargs): pass
            def register(self): return True
            def stop(self): pass

        class _Transport:
            def start(self): pass
            def stop(self): pass

        class _Worker:
            created = 0
            def __init__(self, *args, **kwargs):
                type(self).created += 1
            def run(self): pass
            def stop(self): pass

        class _Thread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self):
                self.target()
                main_module._shutdown_event.set()
            def join(self, timeout=None): pass

        config = _Config()
        with patch.object(main_module, "cfg", return_value=config), \
             patch.object(main_module, "setup_logging"), \
             patch.object(main_module, "ClientAuth", _Auth), \
             patch.object(main_module, "TransportFactory") as factory, \
             patch.object(main_module, "CommandExecutor", lambda: object()), \
             patch.object(main_module, "AgentWorker", _Worker), \
             patch.object(main_module, "threading") as threading_module:
            factory.create.return_value = _Transport()
            # main.py's module-level shutdown Event remains the real Event; only Thread is replaced.
            threading_module.Thread = _Thread
            with patch.object(main_module.signal, "signal"):
                main_module._shutdown_event.clear()
                main_module.main()

        self.assertEqual(_Worker.created, 1)


if __name__ == "__main__":
    unittest.main()
