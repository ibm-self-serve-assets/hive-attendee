import logging

_SILENT_PATHS = frozenset(["/api/stream", "/api/csrf", "/api/config", "/api/status"])


class QuietPollFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        status = getattr(record, "status_code", 200)
        if status >= 400:
            return True
        msg = record.getMessage()
        return not any(
            f'"{path} HTTP' in msg or f'"{path}?' in msg
            for path in _SILENT_PATHS
        )
