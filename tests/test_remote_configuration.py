import pytest
from agent.application.remote_configuration import ConfigurationRevision,RemoteConfigurationLifecycle,Ownership
def lifecycle(): return RemoteConfigurationLifecycle(ConfigurationRevision(1,{'trust_root':'local','limit':10,'level':'INFO'}),{'trust_root':Ownership.LOCAL_ONLY,'limit':Ownership.WITH_LIMITS,'level':Ownership.SERVER_MANAGED},{'limit':(1,100)})
def test_apply_is_versioned_bounded_and_rolls_back():
 l=lifecycle(); assert l.stage_apply(ConfigurationRevision(2,{'limit':20}),lambda _:True).values['limit']==20; assert l.rollback().version==1
@pytest.mark.parametrize('values',[{'trust_root':'remote'},{'limit':101}])
def test_protected_or_unsafe_candidate_never_replaces_known_good(values):
 l=lifecycle()
 with pytest.raises(ValueError): l.stage_apply(ConfigurationRevision(2,values),lambda _:True)
 assert l.active.version==1
def test_unhealthy_and_stale_candidate_fail_without_apply():
 l=lifecycle()
 with pytest.raises(RuntimeError): l.stage_apply(ConfigurationRevision(2,{'level':'DEBUG'}),lambda _:False)
 with pytest.raises(ValueError): l.stage_apply(ConfigurationRevision(1,{'level':'DEBUG'}),lambda _:True)
 assert l.active.version==1
