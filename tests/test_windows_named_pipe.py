import os,threading
import pytest
pytestmark=pytest.mark.skipif(os.name!='nt',reason='Windows native transport')
from agent.infrastructure.windows_named_pipe import WindowsNamedPipe
def test_current_user_named_pipe_round_trip_has_os_dacl():
 pipe=WindowsNamedPipe('mt5-agent-test-'+str(os.getpid())); server=pipe.create_server(); received=[]
 def serve():
  win32pipe=None
  import win32pipe as p
  p.ConnectNamedPipe(server,None); received.append(pipe.receive(server)); pipe.send(server,{'ok':True})
 t=threading.Thread(target=serve); t.start(); client=pipe.connect_client(); pipe.send(client,{'request':'health'}); assert pipe.receive(client)=={'ok':True}; t.join(); assert received==[{'request':'health'}]
