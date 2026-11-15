"""Centralised logging setup (console only).

Logs go to stdout, which is what Docker, Kubernetes, Sentry, Grafana/Loki,
Datadog, etc. expect. In production you only swap/add a handler here.

Usage:
    from app.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
"""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[1;31m",
}
RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    """Colours the level name when running in a terminal."""

    def format(self, record: logging.LogRecord) -> str:
        original = record.levelname
        record.levelname = f"{COLORS.get(original, '')}{original}{RESET}"

        try:
            return super().format(record)
        finally:
            record.levelname = original


_configured = False

def setup_logging(level: str | None = None) -> None:
    global _configured
    if _configured:
        return

    level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    formatter_cls = ColorFormatter if sys.stdout.isatty() else logging.Formatter
    handler.setFormatter(formatter_cls(LOG_FORMAT, DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # Our middleware logs requests, so silence uvicorn's duplicate access log
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
