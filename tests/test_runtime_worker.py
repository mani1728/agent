import pytest
from agent.application.runtime_worker import RuntimeWorkerProtocol,WorkerIdentity,WorkerState,SingleWorkerLease
def worker(): return RuntimeWorkerProtocol('session-token',WorkerIdentity('w',1,1,'user','now'))
def msg(operation,id='r',token='session-token',version='1'):return {'token':token,'version':version,'request_id':id,'operation':operation}
def test_ipc_auth_version_allowlist_duplicate_and_shutdown():
 w=worker(); assert w.handle(msg('handshake'))['state']=='ready'; assert w.handle(msg('health','h'))['ok']
 assert w.handle(msg('anything','x'))['code']=='IPC_UNSUPPORTED_OPERATION'; assert w.handle(msg('health','bad',token='no'))['code']=='IPC_AUTHENTICATION_FAILED'
 assert w.handle(msg('health','h'))['code']=='IPC_DUPLICATE_OR_INVALID_REQUEST'; assert w.handle(msg('shutdown','s'))['state']=='stopped'
def test_single_worker_lease_requires_exact_owner():
 lease=SingleWorkerLease(); identity=worker().identity; lease.acquire(identity)
 with pytest.raises(RuntimeError): lease.acquire(identity)
 with pytest.raises(RuntimeError): lease.release(WorkerIdentity('other',1,1,'u','n'))
 lease.release(identity)
