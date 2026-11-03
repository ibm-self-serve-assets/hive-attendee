import logging

_SILENT_PATHS = frozenset(["/api/stream", "/api/config", "/api/status"])


class QuietPollFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn.access args: (client_addr, method, full_path, http_version, status_code)
        args = record.args
        if not (isinstance(args, tuple) and len(args) == 5):
            return True
        _, _, full_path, _, status = args
        if isinstance(status, int) and status >= 400:
            return True
        return str(full_path).split("?", 1)[0] not in _SILENT_PATHS
