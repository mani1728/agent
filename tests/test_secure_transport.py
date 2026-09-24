from pathlib import Path
import pytest
from agent.adapters.secure_transport import KafkaOutboxTransport,MutualTLSConfiguration,HTTPSMutualTLSTransport
def test_kafka_wrapper_delegates_only_durable_message():
 class P:
  def __init__(self):self.calls=[]
  def produce(self,*args):self.calls.append(args)
 p=P(); KafkaOutboxTransport(p).send({'topic':'result','message_id':'m'}); assert p.calls==[('result',{'topic':'result','message_id':'m'})]
def test_mtls_requires_existing_material_and_never_exposes_paths():
 with pytest.raises(ValueError,match='unavailable'): MutualTLSConfiguration('missing','missing','missing').validate()
def test_mtls_client_receives_cert_configuration(tmp_path):
 files=[tmp_path/n for n in ('ca','cert','key')]
 for f in files:f.touch()
 class C:
  def post(self,*args,**kw):self.args=args;self.kw=kw
 c=C(); HTTPSMutualTLSTransport(c,MutualTLSConfiguration(*(str(f) for f in files))).send({'message_id':'m'})
 assert c.kw['verify']==str(files[0]) and c.kw['cert']==(str(files[1]),str(files[2]))
