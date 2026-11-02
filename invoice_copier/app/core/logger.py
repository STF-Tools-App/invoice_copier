"""Ghi log ra file config/run.log (xoay vòng) song song với log trên giao diện."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.paths import config_dir

_LEVELS = {"info": logging.INFO, "ok": logging.INFO, "warn": logging.WARNING, "error": logging.ERROR}
_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("invoice_copier")
        _logger.setLevel(logging.INFO)
        try:
            h = RotatingFileHandler(config_dir() / "run.log", maxBytes=1_000_000,
                                    backupCount=3, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            _logger.addHandler(h)
        except OSError:
            _logger.addHandler(logging.NullHandler())
    return _logger


def log(level: str, msg: str) -> None:
    get_logger().log(_LEVELS.get(level, logging.INFO), msg)
