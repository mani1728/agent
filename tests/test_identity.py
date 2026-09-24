from types import SimpleNamespace
from agent.application.identity import IdentityAuthority
from agent.contracts.models import Command
def command(name='agent.get_status'): return Command('c',name,'1','x','2026-01-01T00:00:00+00:00',{})
def test_enrollment_rotation_revocation_and_fail_closed():
 a=IdentityAuthority('agent','install'); a.enroll('server','secret-one',{'class:read'})
 context=a.authenticate(SimpleNamespace(credential='secret-one')).context; assert context.metadata['agent_id']=='agent' and a.authorize(context,command()).allowed
 assert a.rotate('secret-one','secret-two'); assert not a.authenticate(SimpleNamespace(credential='secret-one')).success
 assert a.revoke('secret-two'); assert not a.authenticate(SimpleNamespace(credential='secret-two')).success
def test_read_does_not_authorize_trade_or_unknown_principal():
 a=IdentityAuthority(); a.enroll('server','credential',{'class:read'}); ctx=a.authenticate(SimpleNamespace(credential='credential')).context
 assert not a.authorize(ctx,command('trade.execute')).allowed and not a.authenticate(SimpleNamespace(credential='unknown')).success
