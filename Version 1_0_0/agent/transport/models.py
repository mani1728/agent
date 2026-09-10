"""
فایل: agent/transport/models.py
مسئولیت: نگهداری قرارداد داده‌های ورودی و خروجی ایجنت
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time
import uuid

@dataclass
class CommandEnvelope:
    """ساختار استاندارد فرمانی که به ایجنت می‌رسد"""
    command_id: str
    target_class: str      # مثال: Mt5_Manager
    target_method: str     # مثال: get_account_info
    params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1      # 0 (High), 1 (Medium), 2 (Low)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    auth_token: Optional[str] = None

@dataclass
class ResponseEnvelope:
    """ساختار استاندارد پاسخی که ایجنت به سرور بازمی‌گرداند (منطبق بر Mt5ResultV1)"""
    correlation_id: str
    status: str            # 'success' یا 'error'
    data: Any = None
    error_message: Optional[str] = None
    schema_version: str = "Mt5ResultV1"
    seq: int = 1
    total: int = 1
    timestamp: float = field(default_factory=time.time)
