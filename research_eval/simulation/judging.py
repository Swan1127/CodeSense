from __future__ import annotations

import json
from typing import Any, Mapping


RATING_DIMENSIONS = (
    "guidance_quality",
    "cognitive_activation",
    "adaptivity",
    "interaction_coherence",
    "learner_agency",
    "answer_restraint",
)
FLAG_FIELDS = (
    "possible_complete_code_leakage",
    "possible_full_step_leakage",
)


def parse_judge_json(content: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (TypeError, ValueError) as exc:
        raise ValueError("judge output is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("judge output must be an object")
    ratings = value.get("ratings")
    flags = value.get("flags")
    evidence = value.get("evidence")
    if not isinstance(ratings, dict) or set(ratings) != set(RATING_DIMENSIONS):
        raise ValueError("judge ratings must contain the six frozen dimensions")
    if any(type(ratings[name]) is not int or not 1 <= ratings[name] <= 5 for name in RATING_DIMENSIONS):
        raise ValueError("judge ratings must be integers in 1..5")
    if not isinstance(flags, dict) or set(flags) != set(FLAG_FIELDS):
        raise ValueError("judge flags must contain the two frozen fields")
    if any(type(flags[name]) is not bool for name in FLAG_FIELDS):
        raise ValueError("judge flags must be booleans")
    if not isinstance(evidence, dict) or set(evidence) != set(RATING_DIMENSIONS):
        raise ValueError("judge evidence must cover every rating dimension")
    if any(not isinstance(evidence[name], str) or not evidence[name].strip() for name in RATING_DIMENSIONS):
        raise ValueError("judge evidence must be non-empty text")
    return {
        "ratings": {name: int(ratings[name]) for name in RATING_DIMENSIONS},
        "flags": {name: bool(flags[name]) for name in FLAG_FIELDS},
        "evidence": {name: evidence[name].strip() for name in RATING_DIMENSIONS},
    }


def judge_trajectory(
    client: Any,
    judge_prompt: str,
    *,
    task_text: str,
    persona_visible: str,
    transcript: str,
) -> dict[str, Any]:
    payload = {
        "task": task_text,
        "observable_learner_behavior": persona_visible,
        "transcript": transcript,
    }
    messages = [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    first = client.complete("judge", judge_prompt, messages, temperature=0.0, max_tokens=800)
    if not first.success:
        return {"technical_failure": first.error_code or str(first.status_code), "raw": first.content}
    try:
        parsed = parse_judge_json(first.content)
        return {**parsed, "technical_failure": "", "raw": first.content, "format_retries": 0}
    except ValueError:
        retry_messages = [
            *messages,
            {"role": "assistant", "content": first.content},
            {
                "role": "user",
                "content": "Only repair the JSON format. Keep all judgments unchanged.",
            },
        ]
        second = client.complete(
            "judge", judge_prompt, retry_messages, temperature=0.0, max_tokens=800
        )
        if not second.success:
            return {"technical_failure": second.error_code or str(second.status_code), "raw": second.content}
        try:
            parsed = parse_judge_json(second.content)
        except ValueError:
            return {"technical_failure": "judge_format_invalid", "raw": second.content}
        return {**parsed, "technical_failure": "", "raw": second.content, "format_retries": 1}
