from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.schemas import LogEntrySchema


class BotLogger:
    def __init__(self, log_file: str | Path | None = None, max_entries: int = 1000) -> None:
        self._log_file = Path(log_file) if log_file else None
        self._lock = threading.RLock()
        self._entries: deque[LogEntrySchema] = deque(maxlen=max_entries)
        self._logger = logging.getLogger("forex_trading_bot")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self._logger.addHandler(stream_handler)

    def _append(self, level: str, message: str, source: str = "system", metadata: dict[str, Any] | None = None) -> LogEntrySchema:
        entry = LogEntrySchema(
            timestamp=datetime.now(UTC),
            level=level.upper(),
            message=message,
            source=source,
            metadata=metadata,
        )
        with self._lock:
            self._entries.append(entry)
            if self._log_file is not None:
                self._log_file.parent.mkdir(parents=True, exist_ok=True)
                with self._log_file.open("a", encoding="utf-8") as file_handle:
                    file_handle.write(json.dumps(entry.model_dump(mode="json")) + "\n")

        log_method = getattr(self._logger, level.lower(), self._logger.info)
        log_method("[%s] %s", source, message)
        return entry

    def debug(self, message: str, source: str = "system", metadata: dict[str, Any] | None = None) -> LogEntrySchema:
        return self._append("debug", message, source, metadata)

    def info(self, message: str, source: str = "system", metadata: dict[str, Any] | None = None) -> LogEntrySchema:
        return self._append("info", message, source, metadata)

    def warning(self, message: str, source: str = "system", metadata: dict[str, Any] | None = None) -> LogEntrySchema:
        return self._append("warning", message, source, metadata)

    def error(self, message: str, source: str = "system", metadata: dict[str, Any] | None = None) -> LogEntrySchema:
        return self._append("error", message, source, metadata)

    def get_logs(self, limit: int = 100) -> list[LogEntrySchema]:
        with self._lock:
            return list(self._entries)[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
