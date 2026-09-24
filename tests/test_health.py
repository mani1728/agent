import pytest
from agent.application.health import HealthController,MaintenanceState
def test_liveness_is_distinct_from_degraded_readiness_and_safe_heartbeat():
 h=HealthController(storage_ok=lambda:True,mt5_ok=lambda:False); s=h.snapshot(); assert s.live and not s.ready and s.reasons==('mt5_unavailable',)
 body=h.heartbeat('agent','1'); assert body['agent_id']=='agent' and 'secret' not in str(body).lower()
def test_quiesce_state_machine_only_transitions_at_safe_boundary():
 h=HealthController(); h.quiesce(); assert h.snapshot().state is MaintenanceState.QUIESCING and not h.snapshot().ready
 h.safe_point(); h.resync(); h.normal(); assert h.snapshot().ready
 with pytest.raises(ValueError): h.resync()
