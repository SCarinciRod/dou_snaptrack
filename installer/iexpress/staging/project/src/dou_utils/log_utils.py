"""
log_utils.py
Configuração central de logging com:
 - Console handler (sempre)
 - File handler rotativo (se log_file configurado)
 - JSON opcional (DOU_LOG_JSON=1)
 - Compatível com chamadas repetidas (idempotente)
"""

from __future__ import annotations
import logging
import json
import os
import threading
from logging.handlers import RotatingFileHandler
from datetime import datetime

try:
    from .settings import SETTINGS  # optional
except Exception:
    class _LoggingFallback:
        level = "INFO"
        json = False
        log_file = "logs/dou.log"
        max_bytes = 1_048_576
        backup_count = 3

    class _SettingsFallback:
        logging = _LoggingFallback()

    SETTINGS = _SettingsFallback()

_LOCK = threading.Lock()
_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage()
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        # Extra
        for k, v in record.__dict__.items():
            if k in ("args", "msg", "levelname", "levelno", "pathname", "filename",
                     "module", "exc_info", "exc_text", "stack_info", "lineno",
                     "funcName", "created", "msecs", "relativeCreated", "thread",
                     "threadName", "processName", "process"):
                continue
            if k.startswith("_"):
                continue
            try:
                json.dumps({k: v})
                data[k] = v
            except Exception:
                data[k] = str(v)
        return json.dumps(data, ensure_ascii=False)


def _ensure_log_dir(path: str):
    try:
        d = os.path.dirname(path)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
    except Exception:
        pass


def configure_logging(level: str | None = None):
    global _CONFIGURED
    with _LOCK:
        if _CONFIGURED:
            return
        log_conf = SETTINGS.logging
        raw_level = level or getattr(log_conf, "level", "INFO")
        chosen_level = getattr(logging, raw_level.upper(), logging.INFO)

        root = logging.getLogger()
        root.setLevel(chosen_level)

        # Limpando handlers prévios (caso já exista algo residual)
        for h in list(root.handlers):
            root.removeHandler(h)

        # Formatter
        if log_conf.json:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
                "%Y-%m-%d %H:%M:%S"
            )

        # Console
        ch = logging.StreamHandler()
        ch.setLevel(chosen_level)
        ch.setFormatter(formatter)
        root.addHandler(ch)

        # Arquivo (rotativo) se log_file definido
        log_file = getattr(log_conf, "log_file", None)
        if log_file:
            _ensure_log_dir(log_file)
            try:
                fh = RotatingFileHandler(
                    log_file,
                    maxBytes=getattr(log_conf, "max_bytes", 1_048_576),
                    backupCount=getattr(log_conf, "backup_count", 3),
                    encoding="utf-8"
                )
                fh.setLevel(chosen_level)
                fh.setFormatter(formatter)
                root.addHandler(fh)
            except Exception as e:
                root.warning("Não foi possível criar file handler", extra={"err": str(e)})

        _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
