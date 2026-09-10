"""
فایل: agent/transport/base.py
مسئولیت: تعریف Interface برای تمام آداپتورهای ارتباطی
"""
# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from .models import CommandEnvelope, ResponseEnvelope


class ITransportClient(ABC):

    @abstractmethod
    def start(self) -> None:
        """راه اندازی اتصالات و هندلرهای شبکه"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """خاتمه تمیز ارتباطات"""
        pass

    @abstractmethod
    def poll_commands(self, timeout_sec: float = 1.0) -> List[CommandEnvelope]:
        """دریافت فرامین جدید"""
        pass

    @abstractmethod
    def send_response(self, response: ResponseEnvelope) -> bool:
        """ارسال نتیجه اجرای یک دستور"""
        pass

    @abstractmethod
    def send_heartbeat(self, agent_status: Dict[str, Any]) -> bool:
        """ارسال وضعیت سلامت ایجنت"""
        pass

    @abstractmethod
    def ack_command(self, command_id: str) -> None:
        """تایید پردازش فرمان"""
        pass
