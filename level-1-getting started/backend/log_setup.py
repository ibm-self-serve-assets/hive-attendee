"""Logging support for the Hive dashboard backend.

Console shows only major events and errors; everything else goes to LOG_FILE.
Wired up through log_config.json (passed to uvicorn with --log-config).
"""
import logging
import re
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "hive-backend.log"

# Pass as `extra=MAJOR` on an INFO record to show it on the console.
MAJOR = {"major": True}


def make_file_handler() -> logging.Handler:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3, encoding="utf-8")


class ConsoleFilter(logging.Filter):
    """Allow warnings/errors, records flagged major, uvicorn's listen line, and failed HTTP requests."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING or getattr(record, "major", False):
            return True
        if record.name == "uvicorn.error":
            msg = record.getMessage()
            return any(s in msg for s in ("running on", "startup complete", "Shutting down"))
        if record.name == "uvicorn.access":
            args = record.args
            return isinstance(args, tuple) and len(args) == 5 and isinstance(args[4], int) and args[4] >= 400
        return False


_BROKER_RE = re.compile(r"rdkafka#(producer|consumer)-\d+")
_TIMING_RE = re.compile(r"\(after \d+ms[^)]*\)")


class KafkaDedupeFilter(logging.Filter):
    """librdkafka retries a failed connection every ~50ms and logs each attempt.
    Emit a given message at most once per window, noting how many were dropped."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        super().__init__()
        self._window = window_seconds
        self._seen: dict = {}  # key -> (last_emit_time, suppressed_count)
        self._lock = threading.Lock()

    def filter(self, record: logging.LogRecord) -> bool:
        key = (record.levelno, _TIMING_RE.sub("", _BROKER_RE.sub(r"rdkafka#\1", record.getMessage())))
        now = time.monotonic()
        with self._lock:
            last, suppressed = self._seen.get(key, (None, 0))
            if last is not None and now - last < self._window:
                self._seen[key] = (last, suppressed + 1)
                return False
            self._seen[key] = (now, 0)
            if len(self._seen) > 500:
                self._seen = {k: v for k, v in self._seen.items() if now - v[0] < self._window}
        if suppressed:
            record.msg = f"{record.getMessage()} (+{suppressed} similar suppressed)"
            record.args = None
        return True
