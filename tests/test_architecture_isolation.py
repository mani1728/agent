from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "agent"


def _python_sources(directory: Path):
    return list(directory.rglob("*.py"))


def test_core_and_contracts_do_not_import_process_or_http_server_apis():
    forbidden = ("http.server", "import signal", "import socket", "MetaTrader5")
    for area in (ROOT / "core", ROOT / "contracts"):
        for path in _python_sources(area):
            source = path.read_text(encoding="utf-8")
            for token in forbidden:
                assert token not in source, f"{path} must not depend on {token}"


def test_application_host_is_transport_and_process_neutral():
    source = (ROOT / "application" / "host.py").read_text(encoding="utf-8")
    for token in ("http.server", "ThreadingHTTPServer", "import signal", "import socket", "MetaTrader5"):
        assert token not in source


def test_process_signal_api_is_confined_to_infrastructure():
    for path in _python_sources(ROOT):
        if path == ROOT / "infrastructure" / "process_signals.py":
            continue
        assert "import signal" not in path.read_text(encoding="utf-8")
