# -*- coding: utf-8 -*-
"""
config_manager.py
-----------------
ماژول مدیریت تنظیمات با قابلیت «هات-پلاگ/هات-ریلُد» از فایل config.json.

ویژگی‌ها:
- پشتیبانی از کامنت داخل JSON (سبک JSONC: // و /* */ و #)
- ست کردن مقادیر پیش‌فرض اگر در فایل نبود
- ریلود خودکار وقتی فایل تغییر کند (بدون نیاز به ری‌استارت برنامه)
- دسترسی ساده با مسیر نقطه‌ای مثل: cfg.get("kafka.bootstrap_servers")

نکته مهم: فایل config.json می‌تواند شامل قالب‌های رشته‌ای باشد؛
برای مثال: "cmd.{client_id}" که با مقدار client.id جایگزین می‌شود.
"""

from __future__ import annotations
import json, os, re, threading, time
from typing import Any, Dict

_DEFAULTS: Dict[str, Any] = {
    "app": {"env": "dev", "hot_reload_check_sec": 2},
    "logging": {
        "level": "INFO", "json": False,
        "file_enabled": True, "file_path": "logs/app.log",
        "max_bytes": 5_000_000, "backup_count": 3
    },
    "kafka": {
        "enabled": True,
        "bootstrap_servers": ["localhost:9092"],
        "client_id": "client-001",
        "group_id": "mt5-service",
        "security_protocol": "PLAINTEXT",
        "sasl_mechanism": "PLAIN",
        "sasl_username": "", "sasl_password": "",
        "acks": "all", "retries": 3, "linger_ms": 5,
        "request_timeout_ms": 30_000,
        "consumer_auto_offset_reset": "latest",
        "enable_auto_commit": True,
        "session_timeout_ms": 45_000,
        "topics": {
            "commands": ["cmd.{client_id}.p0","cmd.{client_id}.p1","cmd.{client_id}.p2"],
            "replies": "server.replies",
            "status": "clients.status"
        }
    },
    "auth": {
        "token_required": False,
        "tokens": {"client-001": "changeme-token"},
        "header_key": "auth_token"
    },
    "mt5": {
        "login": 0, "password": "", "server": "", "path": "",
        "timeout_sec": 10, "symbols": ["EURUSD","XAUUSD"], "timezone": "UTC"
    },
    "executor": {
        "max_workers": 4, "priority_levels": [0,1,2], "queue_maxsize": 100
    }
}

def _strip_json_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    text = re.sub(r"#.*?$", "", text, flags=re.M)
    return text

class HotReloadConfig:
    def __init__(self, path: str = "config.json"):
        self.path = path
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._mtime: float = 0.0
        self._stop = False
        self._load(first_time=True)
        t = threading.Thread(target=self._watch_loop, name="ConfigWatchdog", daemon=True)
        t.start()

    def _watch_loop(self):
        while not self._stop:
            time.sleep(max(1, int(self._data.get("app", {}).get("hot_reload_check_sec", 2))))
            try:
                self._reload_if_modified()
            except Exception:
                pass

    def stop(self):
        self._stop = True

    def _read_file(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(_DEFAULTS, f, ensure_ascii=False, indent=2)
            return dict(_DEFAULTS)
        with open(self.path, "r", encoding="utf-8") as f:
            raw = f.read()
        clean = _strip_json_comments(raw)
        data = json.loads(clean or "{}")
        return data

    def _merge_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        def merge(a, b):
            if not isinstance(a, dict) or not isinstance(b, dict):
                return a if a is not None else b
            out = dict(b)
            for k, v in a.items():
                if isinstance(v, dict) and k in b and isinstance(b[k], dict):
                    out[k] = merge(v, b[k])
                else:
                    out[k] = v
            return out
        return merge(data or {}, _DEFAULTS)

    def _resolve_templates(self, data: Any) -> Any:
        client_id = self._data.get("kafka", {}).get("client_id") or self._data.get("app", {}).get("client_id") or "client-001"
        def resolve(value):
            if isinstance(value, str):
                return value.format(client_id=client_id)
            if isinstance(value, list):
                return [resolve(x) for x in value]
            if isinstance(value, dict):
                return {k: resolve(v) for k, v in value.items()}
            return value
        return resolve(data)

    def _load(self, first_time: bool=False):
        with self._lock:
            data = self._read_file()
            data = self._merge_defaults(data)
            self._data = data
            self._data = self._resolve_templates(self._data)
            try:
                self._mtime = os.path.getmtime(self.path)
            except FileNotFoundError:
                self._mtime = 0.0

    def _reload_if_modified(self):
        try:
            mtime = os.path.getmtime(self.path)
        except FileNotFoundError:
            mtime = 0.0
        if mtime != self._mtime:
            self._load(first_time=False)

    def reload(self):
        self._load(first_time=False)

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            self._reload_if_modified()
            return json.loads(json.dumps(self._data))

    def get(self, path: str, default: Any=None) -> Any:
        with self._lock:
            self._reload_if_modified()
            d = self._data
            for part in path.split("."):
                if isinstance(d, dict) and part in d:
                    d = d[part]
                else:
                    return default
            return d

_cfg_singleton: HotReloadConfig | None = None

def cfg() -> HotReloadConfig:
    global _cfg_singleton
    if _cfg_singleton is None:
        _cfg_singleton = HotReloadConfig("config.json")
    return _cfg_singleton
