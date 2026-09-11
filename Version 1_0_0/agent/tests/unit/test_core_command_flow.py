from __future__ import annotations

import unittest
import sys
import types

from agent.contracts.command import CommandEnvelope
from agent.contracts.response import ResponseEnvelope, ResponseStatus
from agent.security.command_authorizer import AuthorizationRule, CommandAuthorizer


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


if __name__ == "__main__":
    unittest.main()
