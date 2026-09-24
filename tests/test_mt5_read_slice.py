from agent.application.app import build_dispatcher
from agent.contracts.models import Command
from agent.contracts.protocol import CapabilityClass
from agent.application.mt5_read_commands import READ_COMMANDS

class FakeAgent:
    class I: version='0.1.3'; app_name='agent'
    identity=I()
    class S: value='running'
    state=S()
    def health(self): return type('H',(),{'ok':True,'state':self.state,'message':''})()
class FakeMT5:
    def terminal_information(self): return {'connected':True}
    def terminal_version(self): return [5,0,1]
    def account_information(self): return {'login':123}
def command(name,payload={}): return Command('id',name,'1','corr','2026-09-24T00:00:00+00:00',payload)
def test_read_slice_is_explicit_allowlisted_and_deterministic():
    d=build_dispatcher(FakeAgent(),mt5_read_adapter=FakeMT5())
    assert d.dispatch(command('mt5.get_terminal_information')).data == {'result':{'connected':True}}
    assert [x['identifier'] for x in d.capability_manifest('x').to_dict()['commands'] if x['identifier'].startswith('mt5.')] == sorted(READ_COMMANDS)
    assert d.dispatch(command('mt5.symbol_select')).code == 'UNSUPPORTED_COMMAND'
def test_read_slice_requires_empty_contract_and_respects_disablement():
    d=build_dispatcher(FakeAgent(),mt5_read_adapter=FakeMT5()); assert d.dispatch(command('mt5.get_terminal_version',{'symbol':'x'})).data['error']['code'] == 'READ_REQUEST_PAYLOAD_NOT_ALLOWED'
    d._registry.set_class_enabled(CapabilityClass.READ,False); assert d.dispatch(command('mt5.get_terminal_version')).code == 'CAPABILITY_DISABLED'
