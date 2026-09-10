"""
فایل: agent/transport/base.py
مسئولیت: تعریف Interface برای تمام آداپتورهای ارتباطی
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from .models import CommandEnvelope, ResponseEnvelope

class ITransportClient(ABC):

    @abstractmethod
    def start(self) -> None:
        """راه‌اندازی اتصالات، هندلرهای شبکه یا ترد‌های مربوط به ارتباط"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """خاتمه تمیز ارتباطات و بستن سوکت‌ها"""
        pass

    @abstractmethod
    def poll_commands(self, timeout_sec: float = 1.0) -> List[CommandEnvelope]:
        """
        دریافت فرامین جدید از سرور یا Gateway (بدون بلاک کردن نامحدود)
        """
        pass

    @abstractmethod
    def send_response(self, response: ResponseEnvelope) -> bool:
        """
        ارسال نتیجه اجرای یک دستور به سمت Gateway یا Kafka
        """
        pass

    @abstractmethod
    def send_heartbeat(self, agent_status: Dict[str, Any]) -> bool:
        """
        ارسال وضعیت سلامت و منابع سیستم
        """
        pass

    @abstractmethod
    def ack_command(self, command_id: str) -> None:
        """
        تاییدیه دریافت و اتمام پردازش فرمان (جهت جلوگیری از اجرای تکراری)
        """
        pass
