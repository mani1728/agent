"""Non-production, non-trading evidence probe for ADR-001.

This file intentionally calls only initialize/version/terminal_info/account_info
and shutdown.  It never submits, changes, cancels, or otherwise manages trades.
The JSON result excludes account and credential data.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path


REFERENCE_TERMINAL = r"C:\Program Files\MetaTrader 5\terminal64.exe"
SCHEMA_VERSION = 1


def session_id() -> int | None:
    if os.name != "nt":
        return None
    import ctypes

    value = ctypes.c_uint32()
    if ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(value)):
        return value.value
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "adr-001-mt5-runtime-hosting",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "worker": {
            "pid": os.getpid(),
            "session_id": session_id(),
            "identity": f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}",
        },
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "architecture": platform.architecture()[0],
        },
        "mt5": {
            "reference_terminal": REFERENCE_TERMINAL,
            "package_version": None,
            "initialize_success": False,
            "version_available": False,
            "terminal_info_available": False,
            "account_info_attempted": False,
            "account_info_available": False,
            "shutdown_called": False,
            "last_error_code": None,
        },
    }

    try:
        import MetaTrader5 as mt5

        result["mt5"]["package_version"] = getattr(mt5, "__version__", None)
        initialized = bool(mt5.initialize(REFERENCE_TERMINAL, timeout=30_000))
        result["mt5"]["initialize_success"] = initialized
        if initialized:
            result["mt5"]["version_available"] = mt5.version() is not None
            result["mt5"]["terminal_info_available"] = mt5.terminal_info() is not None
            # Read-only; only a boolean is persisted so account data is not recorded.
            result["mt5"]["account_info_attempted"] = True
            result["mt5"]["account_info_available"] = mt5.account_info() is not None
        error = mt5.last_error()
        result["mt5"]["last_error_code"] = error[0] if isinstance(error, tuple) else None
    except Exception as exc:  # Evidence records exception type, never its message.
        result["mt5"]["exception_type"] = type(exc).__name__
    finally:
        if "mt5" in locals():
            try:
                mt5.shutdown()
                result["mt5"]["shutdown_called"] = True
            except Exception as exc:
                result["mt5"]["shutdown_exception_type"] = type(exc).__name__

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0 if result["mt5"]["initialize_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
