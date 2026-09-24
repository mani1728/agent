"""Policy-governed remote configuration with atomic apply and rollback."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

class Ownership(str,Enum): LOCAL_ONLY='local_only'; SERVER_MANAGED='server_managed'; WITH_LIMITS='server_managed_with_limits'
@dataclass(frozen=True)
class ConfigurationRevision:
    version:int; values:Mapping[str,object]
    def __post_init__(self):
        if self.version < 1: raise ValueError('configuration version must be positive')
        object.__setattr__(self,'values',MappingProxyType(dict(self.values)))
class RemoteConfigurationLifecycle:
    """Candidate data never replaces known-good data until its health check passes."""
    def __init__(self, initial:ConfigurationRevision, policy:Mapping[str,Ownership], limits:Mapping[str,tuple[int,int]]=None):
        self._active=initial; self._previous=None; self._policy=dict(policy); self._limits=dict(limits or {})
    @property
    def active(self): return self._active
    def stage_apply(self,candidate:ConfigurationRevision,health_check):
        if candidate.version <= self._active.version: raise ValueError('configuration version is not newer')
        for key,value in candidate.values.items():
            owner=self._policy.get(key)
            if owner is not Ownership.SERVER_MANAGED and owner is not Ownership.WITH_LIMITS: raise ValueError('configuration key is not remotely mutable')
            if owner is Ownership.WITH_LIMITS:
                low,high=self._limits[key]
                if not isinstance(value,int) or not low<=value<=high: raise ValueError('configuration value violates local limits')
        merged=dict(self._active.values); merged.update(candidate.values); staged=ConfigurationRevision(candidate.version,merged)
        if not health_check(staged): raise RuntimeError('configuration health check failed')
        self._previous=self._active; self._active=staged; return staged
    def rollback(self):
        if self._previous is None: raise RuntimeError('no previous known-good configuration')
        self._active,self._previous=self._previous,self._active; return self._active
