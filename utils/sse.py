"""Small helpers for consistent Server-Sent Events responses.

The project has several older SSE endpoints with slightly different payload
shapes.  New endpoints use the ``type`` field while retaining the commonly
used ``content``/``token``/``done`` fields where that is useful for existing
clients.
"""

import json
from typing import Any, Callable, Iterable, Optional

from flask import Response, request, stream_with_context


def wants_sse(req=None) -> bool:
    """Return whether a request explicitly asks for an SSE response."""

    req = req or request
    stream_flag = str(req.args.get("stream", "")).strip().lower()
    if stream_flag in {"1", "true", "yes", "on"}:
        return True
    accept = str(req.headers.get("Accept", "")).lower()
    return "text/event-stream" in accept


def sse_event(payload: Any, event: Optional[str] = None) -> str:
    """Serialize one JSON SSE event and terminate it with a blank line."""

    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {encoded}\n\n"


def sse_response(events: Iterable[str]) -> Response:
    """Create a cache-safe Flask response for an SSE event iterable."""

    return Response(
        stream_with_context(events),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def sse_text_events(
    chunks: Iterable[str],
    *,
    start_message: str = "正在生成回答...",
    done_payload: Optional[dict] = None,
) -> Iterable[str]:
    """Wrap text chunks in the common start/delta/done protocol."""

    yield sse_event({"type": "start", "message": start_message})
    collected = []
    try:
        for chunk in chunks:
            if chunk is None:
                continue
            text = str(chunk)
            if not text:
                continue
            collected.append(text)
            # ``content`` is intentionally kept for older fetch readers.
            yield sse_event({"type": "delta", "content": text})
        payload = {"type": "done", "done": True, "content": "".join(collected)}
        if done_payload:
            payload.update(done_payload)
        yield sse_event(payload)
    except Exception as exc:
        yield sse_event({"type": "error", "error": str(exc), "message": str(exc)})

def sse_blocking_events(
    work: Callable[[], Any],
    *,
    start_message: str = "正在处理...",
) -> Iterable[str]:
    """Expose a structured/blocking operation through the same SSE envelope.

    Structured evaluations still need to finish before their JSON result can
    be trusted.  Sending a start event immediately keeps the browser
    responsive and gives those operations the same transport contract as
    token streams.
    """

    yield sse_event({"type": "start", "message": start_message})
    try:
        result = work()
        if isinstance(result, dict):
            payload = {"type": "done", "done": True, "result": result}
            payload.update(result)
        else:
            payload = {"type": "done", "done": True, "result": result}
        yield sse_event(payload)
    except Exception as exc:
        yield sse_event({"type": "error", "error": str(exc), "message": str(exc)})
