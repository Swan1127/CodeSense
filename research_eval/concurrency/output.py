import json
import re
import threading
from pathlib import Path

from .models import RequestRecord


_SENSITIVE_VALUE_PATTERNS = (
    re.compile(
        r"\bauthorization\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(
        r"\b(api[_-]?key|x-api-key|password|passwd|pwd|cookie)\b\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
)


def _redact_text(value: str) -> str:
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


class JsonlSink:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, record: RequestRecord) -> None:
        payload = {
            field: _redact_text(value) if isinstance(value, str) else value
            for field, value in record.to_dict().items()
        }
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
