from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import time
from typing import Any, Callable, Sequence

import requests


ZHIPU_CHAT_COMPLETIONS_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-4.5-flash"
REQUEST_TIMEOUT_SECONDS = 120
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (2, 4)
_TRANSIENT_STATUS_CODES = {408, 425, 500, 502, 503, 504}
_ALLOWED_ROLES = {"learner", "system", "judge"}
_CONDITION_LABEL = re.compile(r"(?<![A-Za-z0-9_])(?:C[0-2]|A[1-3])(?![A-Za-z0-9_])")


@dataclass(frozen=True)
class RoleResponse:
    role: str
    content: str
    model: str
    status_code: int
    error_code: str
    retries: int
    elapsed_seconds: float
    timestamp_utc: str

    @property
    def success(self) -> bool:
        return 200 <= self.status_code < 300 and bool(self.content) and not self.error_code


class RoleClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: Any | None = None,
        model: str = DEFAULT_MODEL,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self._transport = transport or requests.Session()
        self._sleep = sleep_fn
        self.model = model

    def complete(
        self,
        role: str,
        system_prompt: str,
        messages: Sequence[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> RoleResponse:
        if role not in _ALLOWED_ROLES:
            raise ValueError(f"unsupported role: {role}")
        copied_messages = [
            {"role": str(item["role"]), "content": str(item["content"])}
            for item in messages
        ]
        if role in {"learner", "judge"}:
            serialized = system_prompt + "\n" + json.dumps(
                copied_messages, ensure_ascii=False
            )
            if _CONDITION_LABEL.search(serialized):
                raise ValueError(f"{role} payload contains a condition label")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": str(system_prompt)},
                *copied_messages,
            ],
            "thinking": {"type": "disabled"},
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }
        started = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()
        status_code = 0
        error_code = "upstream_error"
        content = ""
        attempts = 0

        for attempt in range(MAX_ATTEMPTS):
            attempts = attempt + 1
            try:
                response = self._transport.post(
                    ZHIPU_CHAT_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.RequestException:
                error_code = "upstream_error"
                if attempt < MAX_ATTEMPTS - 1:
                    self._sleep(BACKOFF_SECONDS[attempt])
                    continue
                break

            status_code = int(response.status_code)
            try:
                body = response.json()
            except (TypeError, ValueError):
                body = {}

            server_code = _server_error_code(body)
            if status_code == 429 or server_code == "1305":
                error_code = "rate_limited"
                if attempt < MAX_ATTEMPTS - 1:
                    self._sleep(BACKOFF_SECONDS[attempt])
                    continue
                break
            if status_code in _TRANSIENT_STATUS_CODES:
                error_code = "upstream_error"
                if attempt < MAX_ATTEMPTS - 1:
                    self._sleep(BACKOFF_SECONDS[attempt])
                    continue
                break
            if server_code:
                error_code = "upstream_error"
                break

            content = _response_content(body)
            if 200 <= status_code < 300 and content:
                error_code = ""
                break
            error_code = "upstream_error"
            if 200 <= status_code < 300 and attempt < MAX_ATTEMPTS - 1:
                self._sleep(BACKOFF_SECONDS[attempt])
                continue

            break

        return RoleResponse(
            role=role,
            content=content,
            model=self.model,
            status_code=status_code,
            error_code=error_code,
            retries=max(0, attempts - 1),
            elapsed_seconds=time.perf_counter() - started,
            timestamp_utc=timestamp,
        )


def _server_error_code(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    error = body.get("error")
    if isinstance(error, dict) and error.get("code") is not None:
        return str(error["code"])
    if body.get("code") is not None:
        return str(body["code"])
    return ""


def _response_content(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content.strip() if isinstance(content, str) else ""
