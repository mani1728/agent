"""Optional-dependency transport adapters; no business logic or secret logging."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from agent.application.outbox import DurableOutboxDelivery

@dataclass(frozen=True)
class MutualTLSConfiguration:
    ca_file:str; certificate_file:str; private_key_file:str
    def validate(self):
        for value in (self.ca_file,self.certificate_file,self.private_key_file):
            if not isinstance(value,str) or not value.strip() or not Path(value).is_file(): raise ValueError('mTLS material is unavailable')
class KafkaOutboxTransport:
    """A narrow producer wrapper; caller must provide an already configured client."""
    def __init__(self,producer): self._producer=producer
    def send(self,message):
        # Required durable record remains pending until server acknowledgement.
        self._producer.produce(message['topic'],message)
class HTTPSMutualTLSTransport:
    def __init__(self,client,configuration:MutualTLSConfiguration): self._client=client; configuration.validate(); self._configuration=configuration
    def send(self,message): self._client.post('/agent/outbound',json=message,cert=(self._configuration.certificate_file,self._configuration.private_key_file),verify=self._configuration.ca_file)
