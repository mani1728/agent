# MT5 Capability Inventory — v0.1.3

| Agent command / API | Class | Status | Local side effect |
|---|---|---|---|
| `mt5.get_terminal_information` / `terminal_info` | READ | IMPLEMENTED | No |
| `mt5.get_terminal_version` / `version` | READ | IMPLEMENTED | No |
| `mt5.get_account_information` / `account_info` | READ | IMPLEMENTED | No |
| symbol metadata/tick/orders/positions/history reads | READ or TRADE_ANALYSIS as applicable | PLANNED | No assumed side effect |
| `symbol_select` | LOCAL_STATE | EXCLUDED | Yes: selection state |
| `market_book_add` | LOCAL_STATE | EXCLUDED | Yes: subscription |
| `market_book_release` | LOCAL_STATE | EXCLUDED | Yes: subscription release |
| `order_send` | TRADE_EXECUTION | EXCLUDED | Yes: trading |

Implemented commands accept an empty request payload and return an Agent-owned,
JSON-safe structure. They are only reachable through the versioned command registry;
there is no remote function-name dispatch. MT5 errors carry a safe operation/last-error
detail structure and never cause a trade retry. Other inventory entries are not advertised
as executable capabilities.
