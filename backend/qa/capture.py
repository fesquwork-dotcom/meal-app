"""Structured log capture for stress-test metrics (no production instrumentation)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field


_KV_RE = re.compile(r"(\w+)=([^\s]+)")


def parse_log_record(message: str) -> dict[str, str]:
    """Parse space-separated key=value tokens from a log message."""
    return {key: value for key, value in _KV_RE.findall(message)}


@dataclass
class CapturedEvents:
    """Events collected during one generate_menu call."""

    records: list[dict[str, str]] = field(default_factory=list)
    raw_messages: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.raw_messages.append(message)
        parsed = parse_log_record(message)
        if parsed:
            self.records.append(parsed)

    def find_all(self, event_name: str | None = None, **equals: str) -> list[dict[str, str]]:
        matches: list[dict[str, str]] = []
        for record in self.records:
            if event_name and event_name not in " ".join(self.raw_messages):
                # Prefer matching by event= or by key presence in parsed dict.
                pass
            ok = True
            for key, value in equals.items():
                if record.get(key) != value:
                    ok = False
                    break
            if ok and equals:
                matches.append(record)
        return matches

    def messages_containing(self, needle: str) -> list[str]:
        return [msg for msg in self.raw_messages if needle in msg]


class StressLogHandler(logging.Handler):
    """Attach to claude_service / qa loggers for one run."""

    def __init__(self, sink: CapturedEvents) -> None:
        super().__init__(level=logging.DEBUG)
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            return
        self.sink.add(message)


class LogCapture:
    """Context manager that attaches a handler to selected loggers."""

    def __init__(self, logger_names: list[str] | None = None) -> None:
        self.logger_names = logger_names or ["claude_service", "qa.stress"]
        self.events = CapturedEvents()
        self._handler = StressLogHandler(self.events)
        self._loggers: list[logging.Logger] = []

    def __enter__(self) -> CapturedEvents:
        for name in self.logger_names:
            log = logging.getLogger(name)
            log.addHandler(self._handler)
            log.setLevel(logging.DEBUG)
            self._loggers.append(log)
        return self.events

    def __exit__(self, *_exc) -> None:
        for log in self._loggers:
            log.removeHandler(self._handler)
        self._loggers.clear()
