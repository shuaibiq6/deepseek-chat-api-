"""日志配置工具。"""
import logging
import sys

from app.config import settings

LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging() -> None:
    """配置根日志器（幂等）。"""
    root = logging.getLogger()
    if root.handlers:
        return
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
