from datetime import datetime, timedelta, timezone
import pytest
from agent.contracts.errors import ErrorDomain, StructuredError
from agent.contracts.lifecycle import CommandLifecycle, CommandState, RequestedPriority

NOW=datetime(2026,9,24,tzinfo=timezone.utc)
def make(**kw): return CommandLifecycle("server-1","agent.read","1",NOW,requested_priority=RequestedPriority.HIGH,**kw)
def test_transitions_expiry_and_priority_are_deterministic():
    item=make(expires_at=NOW+timedelta(seconds=1)); item=item.transition(CommandState.VALIDATED,NOW).transition(CommandState.QUEUED,NOW)
    assert item.requested_priority is RequestedPriority.HIGH
    assert item.transition(CommandState.RUNNING,NOW+timedelta(seconds=1)).state is CommandState.EXPIRED
def test_cancellation_and_point_of_no_return():
    assert make().transition(CommandState.VALIDATED,NOW).transition(CommandState.QUEUED,NOW).cancel().state is CommandState.CANCELLED
    running=make().transition(CommandState.VALIDATED,NOW).transition(CommandState.QUEUED,NOW).transition(CommandState.RUNNING,NOW).mark_point_of_no_return()
    with pytest.raises(ValueError,match="COMMAND_CANCELLED"): running.cancel()
def test_invalid_transition_and_ttl_precedence_and_utc():
    with pytest.raises(ValueError,match="INVALID_STATE_TRANSITION"): make().transition(CommandState.SUCCEEDED,NOW)
    assert CommandLifecycle.with_ttl(received_at=NOW,server_command_id="x",command_identifier="x",command_version="1",ttl=timedelta(seconds=1),default_ttl=timedelta(days=1)).expires_at == NOW+timedelta(seconds=1)
def test_structured_error_distinguishes_retry_from_ambiguity():
    error=StructuredError("EXECUTION_AMBIGUOUS",ErrorDomain.MT5,"Outcome unknown",NOW,retryable=True,ambiguous=True,details={"retcode":1})
    assert error.to_dict()["ambiguous"] is True and error.to_dict()["retryable"] is True
