import io
import json
import logging
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent import __version__
from agent.main import run
from agent.application.diagnostics import diagnose
from agent.contracts.configuration import AgentConfig, ConfigurationError, LoggingConfig
from agent.contracts.models import AgentIdentity
from agent.contracts.operational_observability import OperationalEvent, OperationalEventType
from agent.infrastructure.environment_config import EnvironmentConfigurationProvider
from agent.infrastructure.terminal_inspection import TerminalInspection, inspect_terminal
from agent.infrastructure.logging_observability import (
    LoggingOperationalObservability, configure_logging, safe_log,
)
from agent.adapters.mt5_adapter import MT5Adapter
from agent.composition import compose_agent

READY = TerminalInspection(True, (r'C:\MT5\terminal64.exe',), False, True)


@pytest.fixture(autouse=True)
def restore_logging(monkeypatch):
    import os
    for key in os.environ:
        if key.startswith('MT5_AGENT_'):
            monkeypatch.delenv(key)
    logger = logging.getLogger('agent')
    handlers, level, propagate = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = []
    yield
    for h in logger.handlers:
        if h not in handlers:
            h.close()
    logger.handlers, logger.level, logger.propagate = handlers, level, propagate


def test_version_has_no_dependency_or_host_side_effects(capsys, monkeypatch):
    monkeypatch.setenv('MT5_AGENT_HTTP_PORT', 'invalid')
    monkeypatch.setattr('agent.composition.compose_agent', lambda *a: pytest.fail('host created'))
    monkeypatch.setattr('importlib.import_module', lambda *a: pytest.fail('dependency imported'))
    assert run(['--version']) == 0
    assert capsys.readouterr().out.strip() == __version__ == AgentIdentity().version


def test_version_module_entry_point():
    result = subprocess.run([sys.executable, '-m', 'agent', '--version'], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert result.stdout.strip() == __version__
    assert not result.stderr


@pytest.mark.parametrize('json_mode', [True, False])
def test_diagnose_success_no_host_or_file(capsys, monkeypatch, tmp_path, json_mode):
    log_path = tmp_path / 'must-not-exist.log'
    monkeypatch.setenv('MT5_AGENT_LOG_FILE', str(log_path))
    monkeypatch.setattr('agent.infrastructure.terminal_inspection.inspect_terminal', lambda: READY)
    monkeypatch.setattr('agent.composition.compose_agent', lambda *a: pytest.fail('host created'))
    assert run(['--diagnose'] + (['--json'] if json_mode else [])) == 0
    output = capsys.readouterr()
    if json_mode:
        result = json.loads(output.out)
        assert result['ready'] is True
        assert result['agent_version'] == __version__
        assert result['configuration']['http_port'] == 8080
    else:
        assert 'Ready: True' in output.out
    assert not log_path.exists()
    assert not output.err


@pytest.mark.parametrize('inspection', [
    replace(READY, paths=()), replace(READY, dependency_available=False),
    replace(READY, process_running=None), replace(READY, errors=('probe_failed',)),
    replace(READY, supported=False),
])
def test_diagnostic_failed_required_checks(inspection, monkeypatch, capsys):
    monkeypatch.setattr('agent.infrastructure.terminal_inspection.inspect_terminal', lambda: inspection)
    assert run(['--diagnose', '--json']) == 1
    assert json.loads(capsys.readouterr().out)['ready'] is False


def test_diagnostic_bad_configuration_no_secret_leak(monkeypatch, capsys):
    monkeypatch.setenv('MT5_AGENT_HTTP_PORT', 'password=private-token')
    monkeypatch.setenv('MT5_PASSWORD', 'private-token')
    monkeypatch.setattr('agent.infrastructure.terminal_inspection.inspect_terminal', lambda: READY)
    assert run(['--diagnose', '--json']) == 1
    output = capsys.readouterr().out
    assert not json.loads(output)['configuration']['valid']
    assert 'private-token' not in output


def test_json_requires_diagnose():
    with pytest.raises(SystemExit) as exc:
        run(['--json'])
    assert exc.value.code == 2


@pytest.mark.parametrize('level', ['DEBUG', 'INFO', 'WARNING', 'ERROR', ' debug '])
def test_log_configuration_levels(level):
    assert EnvironmentConfigurationProvider({'MT5_AGENT_LOG_LEVEL': level}).load().logging.level == level.strip().upper()


@pytest.mark.parametrize('value', ['TRACE', '', 'password=secret'])
def test_bad_log_level_is_sanitized(value):
    with pytest.raises(ConfigurationError) as exc:
        EnvironmentConfigurationProvider({'MT5_AGENT_LOG_LEVEL': value}).load()
    assert value not in str(exc.value) or value == ''


def test_default_info_debug_filter_and_file(tmp_path):
    assert AgentConfig().logging.level == 'INFO'
    stream = io.StringIO()
    path = tmp_path / 'agent.log'
    logger = configure_logging(LoggingConfig(file=str(path)), stream)
    safe_log(logger, logging.DEBUG, 'debug-marker')
    safe_log(logger, logging.INFO, 'info-marker')
    assert 'info-marker' in stream.getvalue() and 'debug-marker' not in stream.getvalue()
    assert 'info-marker' in path.read_text()
    configure_logging(LoggingConfig('DEBUG'), stream)
    safe_log(logger, logging.DEBUG, 'debug-marker')
    assert 'debug-marker' in stream.getvalue()
    assert len(logger.handlers) == 1


def test_log_file_failure_and_broken_sink_are_nonfatal(tmp_path):
    stream = io.StringIO()
    logger = configure_logging(LoggingConfig(file=str(tmp_path / 'missing/agent.log')), stream)
    assert 'continuing with console' in stream.getvalue()
    class Broken(io.StringIO):
        def write(self, value):
            raise OSError('secret-token')
    configure_logging(LoggingConfig(), Broken())
    safe_log(logger, logging.INFO, 'message')


def test_lifecycle_logging_and_metadata_allowlist():
    stream = io.StringIO()
    logger = configure_logging(LoggingConfig('DEBUG'), stream)
    observer = LoggingOperationalObservability(logger)
    for kind in OperationalEventType:
        observer.record(OperationalEvent.now('id', kind, 'source-secret', 'outcome-secret',
                                            {'password': 'password-secret', 'token': 'token-secret'}))
    output = stream.getvalue()
    for phrase in ['Application startup requested', 'MT5 connection established',
                   'Application host starting', 'Application host stopped', 'Application startup failed']:
        assert phrase in output
    assert 'secret' not in output


def test_real_composition_uses_logging_observer_with_fake_runtime():
    stream = io.StringIO()
    configure_logging(LoggingConfig(), stream)
    mt5 = SimpleNamespace(connect=lambda: True, disconnect=lambda: True, is_connected=lambda: True)
    hosting = SimpleNamespace(serve=lambda: None)
    assert compose_agent(AgentConfig(), mt5=mt5, hosting=hosting).host.run().ok
    assert 'Agent started; MT5 connection established' in stream.getvalue()
    assert 'Application host stopped' in stream.getvalue()


def test_adapter_keeps_vendor_auto_discovery_and_sanitizes_failures():
    stream = io.StringIO()
    logger = configure_logging(LoggingConfig('DEBUG'), stream)
    calls = []
    module = SimpleNamespace(initialize=lambda: calls.append('initialize') or True,
                             shutdown=lambda: calls.append('shutdown'), terminal_info=lambda: object())
    adapter = MT5Adapter(logger, module=module, inspector=lambda: READY)
    assert adapter.connect() and adapter.is_connected() and adapter.disconnect()
    assert calls == ['initialize', 'shutdown']
    def fail():
        raise RuntimeError('password=private-token')
    module.initialize = fail
    assert not adapter.connect()
    assert 'private-token' not in stream.getvalue()
    assert 'initialized and connected successfully' in stream.getvalue()


def test_inspection_finds_portable_terminal_without_starting_it(tmp_path):
    terminal = tmp_path / 'Broker/terminal64.exe'
    terminal.parent.mkdir()
    terminal.write_bytes(b'not executable')
    result = inspect_terminal(roots=[tmp_path], registry_reader=lambda: [],
                              process_probe=lambda: False, dependency_probe=lambda: True, platform='nt')
    assert result.paths == (str(terminal.resolve()),)
    assert not result.errors
    assert result.process_running is False


def test_inspection_reports_probe_errors_without_exception_contents(tmp_path):
    def fail():
        raise OSError('private-token')
    result = inspect_terminal(roots=[tmp_path], registry_reader=fail,
                              process_probe=fail, dependency_probe=fail, platform='nt')
    assert result.process_running is None
    assert not result.dependency_available
    assert result.errors == ('process_inspection_failed', 'registry_inspection_failed')
    assert 'private-token' not in str(result)


def test_non_windows_diagnostics_fail_safely():
    result = inspect_terminal(platform='posix')
    assert result.errors == ('unsupported_platform',)
    assert not result.supported


def test_missing_mt5_dependency_diagnostic_is_not_ready(monkeypatch):
    from agent.infrastructure.terminal_inspection import dependency_available
    def missing(name):
        raise ImportError('secret-token')
    monkeypatch.setattr('importlib.import_module', missing)
    assert dependency_available() is False


def test_broken_observability_logger_does_not_interrupt_events():
    class BrokenLogger:
        def log(self, *args):
            raise OSError('sink unavailable')
    observer = LoggingOperationalObservability(BrokenLogger())
    observer.record(OperationalEvent.now('id', OperationalEventType.APPLICATION_STARTED, 'host', 'ok'))


def test_shutdown_request_is_logged_without_starting_server():
    from agent.infrastructure.http_server_host import HTTPServerHost
    stream = io.StringIO()
    configure_logging(LoggingConfig(), stream)
    host = HTTPServerHost(lambda: pytest.fail('must not bind'))
    host.shutdown()
    assert 'Shutdown requested' in stream.getvalue()


def test_normal_cli_path_keeps_host_and_signal_lifecycle(monkeypatch):
    from agent.contracts.models import Status
    events = []
    fake = SimpleNamespace(hosting=SimpleNamespace(shutdown=lambda: None),
                           host=SimpleNamespace(run=lambda: events.append('run') or Status(True)))
    monkeypatch.setattr('agent.composition.compose_agent', lambda config: events.append('compose') or fake)
    monkeypatch.setattr('agent.infrastructure.process_signals.install_shutdown_signal_handlers',
                        lambda callback: events.append('signals'))
    assert run([]) == 0
    assert events == ['compose', 'signals', 'run']


def test_invalid_logging_config_preserves_exit_two(monkeypatch, capsys):
    monkeypatch.setenv('MT5_AGENT_LOG_LEVEL', 'SECRET-INVALID')
    assert run([]) == 2
    error = capsys.readouterr().err
    assert 'Invalid startup configuration' in error and 'SECRET-INVALID' not in error


def test_unexpected_inspection_failure_is_json_not_traceback(monkeypatch, capsys):
    def fail():
        raise RuntimeError('token=secret')
    monkeypatch.setattr('agent.infrastructure.terminal_inspection.inspect_terminal', fail)
    assert run(['--diagnose', '--json']) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)['terminal']['errors'] == ['inspection_failed']
    assert 'secret' not in output.out and not output.err

@pytest.mark.parametrize('output,expected', [
    ('"python.exe","123","Console","1","12 K"\n', False),
    ('"terminal64.exe","123","Console","1","12 K"\n', True),
    ('"TERMINAL.EXE","456","Console","1","12 K"\n', True),
])
def test_process_inventory_only_reads_tasklist(monkeypatch, output, expected):
    from agent.infrastructure.terminal_inspection import process_running
    def inventory(args, **kwargs):
        assert args[0].endswith('tasklist.exe')
        assert kwargs['timeout'] == 10
        return SimpleNamespace(stdout=output)
    monkeypatch.setattr('subprocess.run', inventory)
    assert process_running() is expected


def test_malformed_process_inventory_is_unknown(monkeypatch):
    from agent.infrastructure.terminal_inspection import process_running
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(stdout='unavailable'))
    with pytest.raises(ValueError):
        process_running()
