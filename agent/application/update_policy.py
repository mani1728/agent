"""Verification and rollout policy only; it never downloads or executes packages."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
@dataclass(frozen=True)
class UpdateCandidate:
    version:str; sha256_hex:str; signer_id:str
class UpdatePolicy:
    def __init__(self, trusted_signers): self._trusted=frozenset(trusted_signers); self._last_known_good=None
    def verify(self,candidate,path):
        if not candidate.version or candidate.signer_id not in self._trusted: return False
        digest=sha256(Path(path).read_bytes()).hexdigest()
        return digest==candidate.sha256_hex
    def stage(self,candidate,path):
        if not self.verify(candidate,path): raise ValueError('update verification failed')
        return candidate
    def commit_after_health(self,candidate,healthy):
        if not healthy: raise RuntimeError('update health check failed')
        self._last_known_good=candidate; return candidate
    @property
    def last_known_good(self): return self._last_known_good
