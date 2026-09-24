from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

class ErrorDomain(str, Enum):
    AGENT="agent"; VALIDATION="validation"; AUTHORIZATION="authorization"; CONFIGURATION="configuration"; MT5="mt5"; BROKER="broker"; TRANSPORT="transport"; STORAGE="storage"; UPDATE="update"

@dataclass(frozen=True)
class StructuredError:
    code: str
    domain: ErrorDomain
    message: str
    timestamp: datetime
    retryable: bool = False
    ambiguous: bool = False
    server_command_id: str | None = None
    agent_execution_id: str | None = None
    details: Mapping[str, Any] = None
    def __post_init__(self):
        if not self.code or not self.message: raise ValueError("error code and message must be non-empty")
        if self.timestamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        object.__setattr__(self,"timestamp",self.timestamp.astimezone(timezone.utc)); object.__setattr__(self,"details",MappingProxyType(dict(self.details or {})))
    def to_dict(self): return {"code":self.code,"domain":self.domain.value,"message":self.message,"timestamp":self.timestamp.isoformat(),"retryable":self.retryable,"ambiguous":self.ambiguous,"server_command_id":self.server_command_id,"agent_execution_id":self.agent_execution_id,"details":dict(self.details)}
