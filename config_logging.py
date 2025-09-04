# -*- coding: utf-8 -*-
import logging, logging.handlers, json, sys, time
from typing import Any, Dict
from config_manager import cfg

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)

def setup_logging() -> None:
    c = cfg().get_all()
    log_cfg: Dict[str, Any] = c.get("logging", {})
    level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    as_json = bool(log_cfg.get("json", False))
    file_enabled = bool(log_cfg.get("file_enabled", True))
    file_path = str(log_cfg.get("file_path", "logs/app.log"))
    max_bytes = int(log_cfg.get("max_bytes", 5_000_000))
    backup_count = int(log_cfg.get("backup_count", 3))

    root = logging.getLogger()
    root.setLevel(level)

    for h in list(root.handlers):
        root.removeHandler(h)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(JsonFormatter() if as_json else logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root.addHandler(stream_handler)

    if file_enabled:
        fh = logging.handlers.RotatingFileHandler(file_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(JsonFormatter() if as_json else logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(fh)
