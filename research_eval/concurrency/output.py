import json
import re
import threading
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .models import RequestRecord


_SENSITIVE_VALUE_PATTERNS = (
    re.compile(
        r"\bauthorization\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(
        r"\b(api[_-]?key|x-api-key|password|passwd|pwd|cookie|access[_-]?token|client[_-]?secret|secret|token)\b\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
)
_URL_PATTERN = re.compile(r"https?://[^\s,;]+", re.IGNORECASE)
_SAFE_ERROR_CODE = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")
_REQUEST_KEY_FIELDS = ("run_id", "level", "request_index", "target", "request_kind")


def _normalize_url(match: re.Match[str]) -> str:
    parts = urlsplit(match.group(0))
    host = parts.hostname
    if not host:
        return "[REDACTED_URL]"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _redact_text(value: str) -> str:
    value = _URL_PATTERN.sub(_normalize_url, value)
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _normalize_error_code(value: str) -> str:
    value = _redact_text(value)
    if not value or _SAFE_ERROR_CODE.fullmatch(value):
        return value
    return "redacted_error"


def _normalize_payload(payload: dict) -> dict:
    normalized = {
        field: _redact_text(value) if isinstance(value, str) else value
        for field, value in payload.items()
    }
    error_code = normalized.get("error_code")
    if isinstance(error_code, str):
        normalized["error_code"] = _normalize_error_code(error_code)
    return normalized


def _request_key(payload: dict) -> tuple:
    return tuple(payload[field] for field in _REQUEST_KEY_FIELDS)


class JsonlSink:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._request_keys = self._load_existing_keys()

    def _load_existing_keys(self) -> set[tuple]:
        if not self.path.exists():
            return set()

        keys = set()
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = _normalize_payload(json.loads(line))
                    keys.add(_request_key(payload))
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
        return keys

    def append(self, record: RequestRecord) -> None:
        payload = _normalize_payload(record.to_dict())
        key = _request_key(payload)
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            if key in self._request_keys:
                return
            self._request_keys.add(key)
            try:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
                    handle.flush()
            except Exception:
                self._request_keys.discard(key)
                raise
