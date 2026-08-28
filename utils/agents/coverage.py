from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple


_DEFAULT_MIN_COVERAGE = 0.8
_DEFAULT_MAX_PROBES = 2
_DEFAULT_DIMENSIONS = ("core", "edge_case", "application")
_ALLOWED_ASSESSMENTS = frozenset({"covered", "partial", "off_topic"})
_MEANINGLESS_EVIDENCE = frozenset({"none", "n/a", "不知道", "无", "没有"})
_ACKNOWLEDGEMENT_TOKENS = frozenset({
    "好的", "收到", "明白了", "懂了", "懂啦", "会了", "知道了", "谢谢", "嗯", "嗯嗯",
    "ok", "okay", "yes", "yep", "got", "it", "understand", "understood", "thanks", "thank", "you",
    "sense",
})
_GENERIC_NON_EXPLANATORY_TOKENS = frozenset({
    "知识点", "有关", "重要", "注意", "细节", "题目", "this", "that", "important", "detail",
})
_EN_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "so", "the", "to", "too", "was", "will", "with",
})
_ACKNOWLEDGEMENT_PATTERNS = (
    re.compile(r"^(?:好(?:的)?|收到|明白了|懂了|懂啦|会了|知道了|谢谢|嗯|嗯嗯)+$"),
    re.compile(r"^(?:ok(?:ay)?|yes|yep|got\s+it|i\s+understand|understood|thanks?|thank\s+you)+$", re.IGNORECASE),
)
_GENERIC_FILLER_PATTERNS = (
    re.compile(r"^(?:这个|这题|这个知识点).{0,8}(?:很重要|有关|要注意|需要注意).{0,4}$"),
    re.compile(r"^(?:it|this).{0,12}(?:makes sense|is important).{0,4}$", re.IGNORECASE),
)
_REASONING_PATTERNS = (
    re.compile(r"(为什么|说明|意味着|表明|用来|这样写|不完整|说不清|讲不清|解释)"),
    re.compile(r"\b(means|shows|explains?|uses?|stops?|keeps?|reads?|causes?|turns?)\b", re.IGNORECASE),
)
_CLAUSE_RELATION_PATTERNS = (
    re.compile(r"(再.{0,8}就|多.{0,8}就|少.{0,8}就|前一.{0,4}后一|停在.{0,8}前)"),
    re.compile(r"\b(one more|extra pass|past the array|last valid|stops before|ends at)\b", re.IGNORECASE),
)
_CODE_RELATION_PATTERN = re.compile(
    r"(?<!\w)([A-Za-z_][A-Za-z0-9_\[\]\.\-\+\s]*|\d+\s*[\+\-]\s*\d+|\d+)\s*"
    r"(<=|>=|==|!=|<|>|=|\+|-)\s*"
    r"([A-Za-z_][A-Za-z0-9_\[\]\.\-\+\s]*|\d+\s*[\+\-]\s*\d+|\d+)(?!\w)"
)


@dataclass(frozen=True)
class CoverageConfig:
    min_coverage: float = _DEFAULT_MIN_COVERAGE
    max_probes_per_concept: int = _DEFAULT_MAX_PROBES
    probe_dimensions: Tuple[str, ...] = _DEFAULT_DIMENSIONS


@dataclass(frozen=True)
class CoverageDecision:
    concept_status: str
    attempts: int
    next_concept: Optional[str]
    next_dimension: Optional[str]
    ready_for_code: bool
    coverage_score: float
    state_patch: Dict[str, Any]


def load_coverage_config(raw: Any, key_concepts: Any) -> CoverageConfig:
    concepts = _normalize_key_concepts(key_concepts)
    candidate = raw.get("feynman_coverage") if isinstance(raw, Mapping) else None
    if not isinstance(candidate, Mapping):
        candidate = raw if isinstance(raw, Mapping) and "min_coverage" in raw else {}

    min_coverage = candidate.get("min_coverage", _DEFAULT_MIN_COVERAGE)
    max_probes = candidate.get("max_probes_per_concept", _DEFAULT_MAX_PROBES)
    probe_dimensions = candidate.get("probe_dimensions", _DEFAULT_DIMENSIONS)

    if not isinstance(min_coverage, (int, float)) or not 0.0 <= float(min_coverage) <= 1.0:
        raise ValueError("min_coverage must be between 0 and 1")
    if type(max_probes) is not int or max_probes <= 0:
        raise ValueError("max_probes_per_concept must be a positive integer")

    dimensions = _normalize_dimensions(probe_dimensions)
    if concepts and len(dimensions) < max_probes:
        raise ValueError("probe_dimensions must provide at least one unique dimension per probe")

    return CoverageConfig(
        min_coverage=float(min_coverage),
        max_probes_per_concept=max_probes,
        probe_dimensions=dimensions,
    )


def apply_coverage_assessment(
    state: Any,
    key_concepts: Any,
    *,
    config: CoverageConfig,
    concept: Any,
    dimension: Any,
    assessment: Any,
    evidence: Any,
    event_id: Any,
) -> CoverageDecision:
    concepts = _normalize_key_concepts(key_concepts)
    current_concept = _require_member("concept", concept, concepts)
    current_dimension = _require_member("dimension", dimension, config.probe_dimensions)
    current_assessment = _require_member("assessment", assessment, _ALLOWED_ASSESSMENTS)
    evidence_text = _normalize_evidence(evidence)
    event_token = _normalize_token("event_id", event_id)

    coverage = _normalized_coverage(getattr(state, "concept_coverage", []), concepts)
    entry = coverage[current_concept]
    if entry["attempts"] >= config.max_probes_per_concept:
        raise ValueError("max probes reached for concept")
    if current_dimension in entry["used_dimensions"]:
        raise ValueError("dimension already used for concept")
    if current_assessment in {"covered", "partial"} and not _is_concrete_explanation(evidence_text):
        raise ValueError("concrete evidence is required for covered or partial assessments")

    updated = dict(entry)
    updated["attempts"] = entry["attempts"] + 1
    updated["used_dimensions"] = [*entry["used_dimensions"], current_dimension]
    updated["attempt_event_ids"] = [*entry["attempt_event_ids"], event_token]
    updated["last_evidence_event_id"] = event_token

    if current_assessment == "covered":
        updated["status"] = "covered"
        updated["accepted_evidence_count"] = entry["accepted_evidence_count"] + 1
        updated["evidence_event_ids"] = [*entry["evidence_event_ids"], event_token]
    else:
        updated["status"] = current_assessment

    coverage[current_concept] = updated
    ordered_coverage = [coverage[name] for name in concepts]
    next_concept, next_dimension = _next_probe(coverage, concepts, config)
    coverage_score = _coverage_score(ordered_coverage)
    pending_probe = (
        {"concept": next_concept, "dimension": next_dimension}
        if next_concept is not None and next_dimension is not None
        else None
    )
    unresolved = [
        item["concept"]
        for item in ordered_coverage
        if item["status"] != "covered"
    ]
    ready_for_code = pending_probe is None and coverage_score >= config.min_coverage

    return CoverageDecision(
        concept_status=updated["status"],
        attempts=updated["attempts"],
        next_concept=next_concept,
        next_dimension=next_dimension,
        ready_for_code=ready_for_code,
        coverage_score=coverage_score,
        state_patch={
            "concept_coverage": ordered_coverage,
            "coverage_score": coverage_score,
            "unresolved_concepts": unresolved,
            "ready_for_code": ready_for_code,
            "pending_probe": pending_probe,
        },
    )


def _normalize_key_concepts(key_concepts: Any) -> List[str]:
    if not isinstance(key_concepts, list):
        return []
    seen = set()
    concepts: List[str] = []
    for value in key_concepts:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        concepts.append(text)
    return concepts


def _normalize_dimensions(raw: Any) -> Tuple[str, ...]:
    if isinstance(raw, tuple):
        values = list(raw)
    elif isinstance(raw, list):
        values = raw
    else:
        raise ValueError("probe_dimensions must be a list or tuple")

    seen = set()
    dimensions: List[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("probe_dimensions entries must be strings")
        text = value.strip()
        if not text:
            raise ValueError("probe_dimensions entries must not be empty")
        if text in seen:
            raise ValueError("probe_dimensions entries must be unique")
        seen.add(text)
        dimensions.append(text)
    if not dimensions:
        raise ValueError("probe_dimensions must not be empty")
    return tuple(dimensions)


def _require_member(name: str, value: Any, allowed: Any) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a non-empty string")
    text = value.strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    if text not in allowed:
        raise ValueError(f"invalid {name}: {value!r}")
    return text


def _normalize_evidence(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("evidence must be a non-empty string")
    text = value.strip()
    if not text or text.casefold() in _MEANINGLESS_EVIDENCE:
        raise ValueError("evidence must be meaningful")
    return text


def _is_concrete_explanation(text: str) -> bool:
    normalized = _normalize_free_text(text)
    if not normalized:
        return False

    if _is_acknowledgement_or_filler(text, normalized):
        return False
    if _substantive_character_count(text) < 8:
        return False
    if _has_complete_code_relation(text) and _has_substantive_detail(text):
        return True
    if _has_explanatory_structure(text):
        return True
    if _has_multiclause_relation(text):
        return True
    return False


def _is_acknowledgement_or_filler(text: str, normalized: str) -> bool:
    stripped = text.strip()
    if any(pattern.fullmatch(stripped) for pattern in _ACKNOWLEDGEMENT_PATTERNS):
        return True
    if any(pattern.fullmatch(stripped) for pattern in _GENERIC_FILLER_PATTERNS):
        return True

    tokens = _word_tokens(stripped)
    cjk_phrases = _cjk_phrases(stripped)
    ack_hits = sum(token in _ACKNOWLEDGEMENT_TOKENS for token in tokens) + sum(
        phrase in _ACKNOWLEDGEMENT_TOKENS for phrase in cjk_phrases
    )
    generic_hits = sum(token in _GENERIC_NON_EXPLANATORY_TOKENS for token in tokens) + sum(
        phrase in _GENERIC_NON_EXPLANATORY_TOKENS for phrase in cjk_phrases
    )
    substantive_tokens = [
        token for token in tokens
        if len(token) >= 3 and token not in _EN_STOPWORDS and token not in _ACKNOWLEDGEMENT_TOKENS
    ]
    substantive_phrases = [
        phrase for phrase in cjk_phrases
        if len(phrase) >= 2 and phrase not in _ACKNOWLEDGEMENT_TOKENS and phrase not in _GENERIC_NON_EXPLANATORY_TOKENS
    ]
    if ack_hits and not substantive_tokens and not substantive_phrases:
        return True
    if generic_hits and not _has_complete_code_relation(text) and not _has_clause_detail(text):
        return True
    if normalized in {"if", "because", "1", "okbecause", "iunderstandif"}:
        return True
    return False


def _substantive_character_count(text: str) -> int:
    return sum(1 for char in text if char.isalnum() or "\u4e00" <= char <= "\u9fff")


def _has_complete_code_relation(text: str) -> bool:
    for match in _CODE_RELATION_PATTERN.finditer(text):
        left = match.group(1).strip()
        operator = match.group(2)
        right = match.group(3).strip()
        if not left or not right:
            continue
        if left.isdigit() and right.isdigit() and operator == "=":
            continue
        if not any(char.isalpha() or char == "_" for char in f"{left}{right}") and "[" not in f"{left}{right}":
            continue
        return True
    return False


def _has_substantive_detail(text: str) -> bool:
    return bool(_has_clause_detail(text) or _has_explanatory_structure(text) or _has_multiclause_relation(text))


def _has_explanatory_structure(text: str) -> bool:
    stripped = text.strip()
    if _has_complete_code_relation(stripped) and len(_split_clauses(stripped)) >= 2:
        return True
    if any(pattern.search(stripped) for pattern in _REASONING_PATTERNS) and _has_clause_detail(stripped):
        return True
    return False


def _has_multiclause_relation(text: str) -> bool:
    clauses = [clause for clause in _split_clauses(text) if _substantive_character_count(clause) >= 4]
    if len(clauses) < 2:
        return False
    if any(pattern.search(text) for pattern in _CLAUSE_RELATION_PATTERNS) and _has_clause_detail(text):
        return True

    repeated_terms = _repeated_substantive_terms(clauses)
    if repeated_terms and any(_has_clause_detail(clause) for clause in clauses):
        return True
    return False


def _has_clause_detail(text: str) -> bool:
    clauses = _split_clauses(text)
    return any(
        len(_word_tokens(clause)) >= 2
        or len(_cjk_phrases(clause)) >= 2
        or _substantive_character_count(clause) >= 10
        or _has_complete_code_relation(clause)
        for clause in clauses
    )


def _split_clauses(text: str) -> List[str]:
    return [
        part.strip()
        for part in re.split(r"[，,。；;：:\n]|但|不过|而且|然后|(?:\bbut\b|\band\b)", text, flags=re.IGNORECASE)
        if part.strip()
    ]


def _repeated_substantive_terms(clauses: List[str]) -> set[str]:
    clause_terms: List[set[str]] = []
    for clause in clauses:
        terms = {
            token for token in _word_tokens(clause)
            if len(token) >= 3 and token not in _EN_STOPWORDS and token not in _ACKNOWLEDGEMENT_TOKENS
        }
        terms.update({
            phrase for phrase in _cjk_phrases(clause)
            if len(phrase) >= 2 and phrase not in _ACKNOWLEDGEMENT_TOKENS and phrase not in _GENERIC_NON_EXPLANATORY_TOKENS
        })
        clause_terms.append(terms)
    repeated: set[str] = set()
    for index, terms in enumerate(clause_terms):
        for other in clause_terms[index + 1:]:
            repeated.update(terms & other)
    return repeated


def _word_tokens(text: str) -> List[str]:
    return [item.casefold() for item in re.findall(r"[A-Za-z]+", text)]


def _cjk_phrases(text: str) -> List[str]:
    return re.findall(r"[\u4e00-\u9fff]{2,}", text)


def _normalize_free_text(value: str) -> str:
    lowered = value.casefold()
    return "".join(char for char in lowered if char.isalnum() or "\u4e00" <= char <= "\u9fff")


def _normalize_token(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _normalized_coverage(raw: Any, concepts: List[str]) -> Dict[str, Dict[str, Any]]:
    ordered = {concept: _empty_entry(concept) for concept in concepts}
    items = []
    if isinstance(raw, Mapping):
        items = [{"concept": key, **value} for key, value in raw.items() if isinstance(value, Mapping)]
    elif isinstance(raw, list):
        items = [item for item in raw if isinstance(item, Mapping)]

    for item in items:
        concept = item.get("concept")
        if concept not in ordered:
            continue
        ordered[concept] = _normalize_entry(item, concept)
    return ordered


def _empty_entry(concept: str) -> Dict[str, Any]:
    return {
        "concept": concept,
        "status": "unseen",
        "attempts": 0,
        "used_dimensions": [],
        "attempt_event_ids": [],
        "accepted_evidence_count": 0,
        "evidence_event_ids": [],
        "last_evidence_event_id": None,
    }


def _normalize_entry(raw: Mapping[str, Any], concept: str) -> Dict[str, Any]:
    entry = _empty_entry(concept)
    status = raw.get("status", entry["status"])
    if isinstance(status, str) and status in {"unseen", "covered", "partial", "off_topic"}:
        entry["status"] = status

    attempts = raw.get("attempts", 0)
    if type(attempts) is int and attempts >= 0:
        entry["attempts"] = attempts

    used_dimensions = raw.get("used_dimensions", [])
    if isinstance(used_dimensions, list):
        entry["used_dimensions"] = [
            item.strip()
            for item in used_dimensions
            if isinstance(item, str) and item.strip()
        ]

    attempt_event_ids = raw.get("attempt_event_ids", [])
    if isinstance(attempt_event_ids, list):
        entry["attempt_event_ids"] = [
            item.strip()
            for item in attempt_event_ids
            if isinstance(item, str) and item.strip()
        ]

    accepted = raw.get("accepted_evidence_count", 0)
    if type(accepted) is int and accepted >= 0:
        entry["accepted_evidence_count"] = accepted

    evidence_event_ids = raw.get("evidence_event_ids", [])
    if isinstance(evidence_event_ids, list):
        entry["evidence_event_ids"] = [
            item.strip()
            for item in evidence_event_ids
            if isinstance(item, str) and item.strip()
        ]

    last_event_id = raw.get("last_evidence_event_id")
    if isinstance(last_event_id, str) and last_event_id.strip():
        entry["last_evidence_event_id"] = last_event_id.strip()
    return entry


def _next_probe(
    coverage: Mapping[str, Dict[str, Any]],
    concepts: List[str],
    config: CoverageConfig,
) -> tuple[Optional[str], Optional[str]]:
    for concept in concepts:
        entry = coverage[concept]
        if entry["status"] == "covered" or entry["attempts"] >= config.max_probes_per_concept:
            continue
        used_dimensions = frozenset(entry["used_dimensions"])
        for dimension in config.probe_dimensions:
            if dimension not in used_dimensions:
                return concept, dimension
    return None, None


def _coverage_score(entries: List[Dict[str, Any]]) -> float:
    if not entries:
        return 0.0
    total_weight = 0.0
    earned_weight = 0.0
    for entry in entries:
        raw_weight = entry.get("weight", 1.0)
        weight = float(raw_weight) if isinstance(raw_weight, (int, float)) and raw_weight > 0 else 1.0
        total_weight += weight
        if entry["status"] == "covered":
            earned_weight += weight
        elif entry["status"] == "partial":
            earned_weight += weight * 0.5
    if total_weight <= 0:
        return 0.0
    score = earned_weight / total_weight
    return max(0.0, min(1.0, score))
