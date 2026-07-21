import hashlib
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .models import RequestRecord


_SAFE_TARGETS = frozenset({"upstream", "platform", "fake"})
_SAFE_REQUEST_KINDS = frozenset({"short", "long", "mixed"})
_SAFE_ERROR_CODES = frozenset(
    {
        "",
        "429",
        "1305",
        "worker_timeout",
        "timeout",
        "http_error",
        "transport_error",
        "unexpected_redirect",
        "redacted_error",
    }
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\bauthorization\s*[:=]\s*[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(
        r"\b(api[_-]?key|password|passwd|pwd|cookie|access[_-]?token|client[_-]?secret|secret|token)\b\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
)
_URI_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s,;]+")
_RUN_ID_HASH = re.compile(r"sha256:[0-9a-f]{16}\Z")
_REQUEST_KEY_FIELDS = ("run_id", "level", "request_index", "target", "request_kind")


def _redact_uri(match: re.Match[str]) -> str:
    parts = urlsplit(match.group(0))
    host = parts.hostname
    if not host:
        return "[REDACTED_URI]"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def _redact_for_defense(value: str) -> str:
    value = _URI_PATTERN.sub(_redact_uri, value)
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _short_hash(value: str) -> str:
    if _RUN_ID_HASH.fullmatch(value):
        return value
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _safe_target(value: str) -> str:
    value = _redact_for_defense(value)
    return value if value in _SAFE_TARGETS else "redacted_target"


def _safe_request_kind(value: str) -> str:
    value = _redact_for_defense(value)
    return value if value in _SAFE_REQUEST_KINDS else "redacted_kind"


def _safe_error_code(value: str) -> str:
    value = _redact_for_defense(value)
    return value if value in _SAFE_ERROR_CODES else "redacted_error"


def _safe_timestamp(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "redacted_timestamp"
    return value


def _serialize_payload(payload: dict) -> dict:
    return {
        "run_id": _short_hash(str(payload["run_id"])),
        "level": int(payload["level"]),
        "request_index": int(payload["request_index"]),
        "target": _safe_target(str(payload["target"])),
        "request_kind": _safe_request_kind(str(payload["request_kind"])),
        "started_at": _safe_timestamp(str(payload["started_at"])),
        "elapsed_seconds": float(payload["elapsed_seconds"]),
        "success": bool(payload["success"]),
        "status_code": int(payload["status_code"]),
        "error_code": _safe_error_code(str(payload["error_code"])),
        "retries": int(payload["retries"]),
        "input_chars": int(payload["input_chars"]),
        "output_chars": int(payload["output_chars"]),
    }


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
                    keys.add(_request_key(_serialize_payload(json.loads(line))))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
        return keys

    def append(self, record: RequestRecord) -> None:
        payload = _serialize_payload(record.to_dict())
        key = _request_key(payload)
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            if key in self._request_keys:
                return
            with self.path.open("a", encoding="utf-8") as handle:
                offset = handle.tell()
                self._request_keys.add(key)
                try:
                    handle.write(line + "\n")
                    handle.flush()
                except BaseException:
                    handle.truncate(offset)
                    handle.flush()
                    self._request_keys.discard(key)
                    raise
