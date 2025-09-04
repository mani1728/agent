# -*- coding: utf-8 -*-
from typing import Optional, Dict, Any
from config_manager import cfg

def validate_token(client_id: str, provided_token: Optional[str]) -> bool:
    c = cfg()
    token_required = bool(c.get("auth.token_required", False))
    if not token_required:
        return True
    tokens: Dict[str, str] = c.get("auth.tokens", {})
    expected = tokens.get(client_id)
    if expected is None:
        return False
    return (provided_token or "") == expected

def extract_token(payload: Dict[str, Any]) -> Optional[str]:
    key = cfg().get("auth.header_key", "auth_token")
    return payload.get(key)
