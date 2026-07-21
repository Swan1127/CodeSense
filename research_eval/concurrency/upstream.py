from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests

from .models import RequestRecord
from .runner import REQUEST_TIMEOUT_SECONDS


ZHIPU_CHAT_COMPLETIONS_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-4.5-flash"
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (2, 4, 8, 16)

PROMPTS = {
    "short": (
        "请用不超过三句话提示一名正在学习数据结构的学生："
        "如何判断单链表是否存在环？不要直接给出完整代码。"
    ),
    "long": (
        "一名学生正在分析带权图的最短路径问题，但混淆了 Dijkstra 算法与"
        "Bellman-Ford 算法的适用条件。请以启发式教师的方式展开一轮较完整的"
        "引导：先提出诊断问题，再解释负权边的影响，最后给出一个用于自检的"
        "小例子。不要直接代写程序。"
    ),
}


class ZhipuTarget:
    def __init__(
        self,
        api_key: str,
        run_id: str,
        request_kind: str,
        session: requests.Session | Any,
        *,
        model: str = DEFAULT_MODEL,
    ) -> None:
        if request_kind not in PROMPTS:
            raise ValueError("request_kind must be short or long")
        if not api_key:
            raise ValueError("api_key must not be empty")
        self._api_key = api_key
        self.run_id = run_id
        self.request_kind = request_kind
        self.session = session
        self.model = model
        self.prompt = PROMPTS[request_kind]

    def call(self, level: int, index: int) -> RequestRecord:
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        status_code = 0
        error_code = "request_error"
        output = ""
        attempts = 0

        for attempt in range(MAX_ATTEMPTS):
            attempts = attempt + 1
            try:
                response = self.session.post(
                    ZHIPU_CHAT_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._payload(),
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except requests.Timeout:
                status_code = 0
                error_code = "timeout"
                if self._retry(attempt):
                    continue
                break
            except requests.ConnectionError:
                status_code = 0
                error_code = "connection_error"
                if self._retry(attempt):
                    continue
                break
            except requests.RequestException:
                status_code = 0
                error_code = "request_error"
                if self._retry(attempt):
                    continue
                break

            status_code = int(response.status_code)
            try:
                body = response.json()
            except (TypeError, ValueError):
                error_code = "429" if status_code == 429 else "non_json_response"
                if status_code == 429 and self._retry(attempt):
                    continue
                break

            error_code = _extract_error_code(body)
            if status_code == 429 or error_code == "1305":
                if not error_code:
                    error_code = "429"
                if self._retry(attempt):
                    continue
                break

            output = _extract_content(body)
            if 200 <= status_code < 300 and output:
                error_code = ""
                break

            if not error_code:
                error_code = (
                    "invalid_response" if 200 <= status_code < 300 else f"http_{status_code}"
                )
            break

        success = 200 <= status_code < 300 and bool(output) and not error_code
        return RequestRecord(
            run_id=self.run_id,
            level=level,
            request_index=index,
            target="zhipu_upstream",
            request_kind=self.request_kind,
            started_at=started_at,
            elapsed_seconds=time.perf_counter() - started,
            success=success,
            status_code=status_code,
            error_code=error_code,
            retries=max(0, attempts - 1),
            input_chars=len(self.prompt),
            output_chars=len(output),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": self.prompt}],
            "thinking": {"type": "disabled"},
            "temperature": 0.2,
            "max_tokens": 800 if self.request_kind == "long" else 300,
        }

    @staticmethod
    def _retry(attempt: int) -> bool:
        if attempt >= MAX_ATTEMPTS - 1:
            return False
        time.sleep(BACKOFF_SECONDS[attempt])
        return True


def _extract_error_code(body: object) -> str:
    if not isinstance(body, dict):
        return "invalid_response"
    error = body.get("error")
    if isinstance(error, dict) and error.get("code") is not None:
        return str(error["code"])
    if body.get("code") is not None:
        return str(body["code"])
    return ""


def _extract_content(body: object) -> str:
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
    return content if isinstance(content, str) else ""
