"""Fail-closed local identity, enrollment, rotation and capability ACL foundation."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4
from agent.contracts.security import AuthenticationResult, AuthorizationDecision, SecurityContext

def token_fingerprint(token: str) -> str:
    if not isinstance(token,str) or not token: raise ValueError("credential is required")
    return sha256(token.encode()).hexdigest()
@dataclass(frozen=True)
class AgentIdentity:
    agent_id: str
    installation_id: str
class IdentityAuthority:
    def __init__(self, agent_id=None, installation_id=None):
        self.identity=AgentIdentity(agent_id or str(uuid4()),installation_id or str(uuid4())); self._credentials={}
    def enroll(self, principal_id, credential, permissions):
        if not principal_id or not permissions: raise ValueError("principal and permissions are required")
        self._credentials[token_fingerprint(credential)]=(principal_id,frozenset(permissions),False)
    def rotate(self, old_credential, new_credential):
        value=self._credentials.get(token_fingerprint(old_credential))
        if value is None or value[2]: return False
        self._credentials[token_fingerprint(old_credential)]=(value[0],value[1],True); self._credentials[token_fingerprint(new_credential)]=(value[0],value[1],False); return True
    def revoke(self, credential):
        key=token_fingerprint(credential); value=self._credentials.get(key)
        if value is None:return False
        self._credentials[key]=(value[0],value[1],True); return True
    def authenticate(self, request):
        credential=getattr(request,"credential",None)
        value=self._credentials.get(token_fingerprint(credential)) if credential else None
        if value is None or value[2]: return AuthenticationResult(False,code="authentication_failed",message="Authentication failed.")
        return AuthenticationResult(True,SecurityContext(value[0],"credential",value[1],{"agent_id":self.identity.agent_id}))
    def authorize(self,context,command):
        permitted=("command:"+command.command_type in context.permissions or "class:read" in context.permissions and command.command_type.startswith(("agent.","mt5.get_")))
        return AuthorizationDecision(permitted,"authorization_denied" if not permitted else "","Authorization denied." if not permitted else "")
