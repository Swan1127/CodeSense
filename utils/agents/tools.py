"""Server-authoritative Stage 3 agent tools.

Tool schemas and permissions live here rather than in model prompts.  Handler
results deliberately keep private artifacts out of ``model_content``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional

from .coverage import CoverageConfig, apply_coverage_assessment
from .contracts import AgentRole, ToolCall, ToolResult
from .memory import MemorySnapshot


MAX_CONCEPT_CHARS = 200
MAX_EVIDENCE_CHARS = 2_000
MAX_FIXED_CODE_CHARS = 8_000
MAX_GOAL_CHARS = 300
MAX_PROBE_DIMENSION_CHARS = 64
MAX_PROBE_QUESTION_CHARS = 500
_SAFE_CODE_REVIEW_MESSAGE = "我写了一版代码，请帮我检查。"
_SAFE_PASSED_FEEDBACK = "修复已通过检查。"
_SAFE_FAILED_FEEDBACK = "请继续检查代码逻辑。"
_SELF_CONFIRMING_PROBE_PATTERNS = (
    re.compile(r"我也(?:懂了|明白了|会了)"),
    re.compile(r"我知道答案"),
    re.compile(r"\b(?:i\s+also\s+understand|i\s+know\s+the\s+answer)\b", re.IGNORECASE),
)
_QUESTION_HINT_PATTERNS = (
    re.compile(r"[?？]\s*$"),
    re.compile(r"(为什么|怎么|如何|是否|能否|能不能|请问)"),
    re.compile(r"\b(why|how|what|which|when|where|could|can|would|do|does|did|is|are)\b", re.IGNORECASE),
)

ToolHandler = Callable[["ToolContext", Dict[str, Any]], ToolResult]
BuggyCodeGenerator = Callable[["ToolContext"], Mapping[str, Any]]
FixEvaluator = Callable[["ToolContext", str], Any]


@dataclass
class ToolContext:
    session_id: int
    request_id: str
    role: AgentRole
    memory: MemorySnapshot
    input_kind: str = "chat"
    target_role: str = ""
    assignment_title: str = ""
    key_concepts: List[str] = field(default_factory=list)
    reference_code: str = ""
    coverage_config: CoverageConfig = field(default_factory=CoverageConfig)
    trigger: Optional[Dict[str, Any]] = None
    executed_results: Dict[str, ToolResult] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    allowed_roles: FrozenSet[AgentRole]
    handler: ToolHandler
    side_effect: bool = False

    def public_spec(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: Dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        self._definitions[definition.name] = definition

    def specs_for(self, role: AgentRole) -> List[Dict[str, Any]]:
        return [
            definition.public_spec()
            for definition in self._definitions.values()
            if role in definition.allowed_roles
        ]

    def is_side_effect(self, name: str) -> bool:
        definition = self._definitions.get(name)
        return bool(definition and definition.side_effect)

    def execute(self, role: AgentRole, call: ToolCall, context: ToolContext) -> ToolResult:
        definition = self._definitions.get(call.name)
        if definition is None:
            return _error("UNKNOWN_TOOL")
        if role is not context.role or role not in definition.allowed_roles:
            return _error("TOOL_NOT_ALLOWED")
        if not self._arguments_match_schema(definition.input_schema, call.arguments):
            return _error("INVALID_TOOL_ARGUMENTS")
        if definition.side_effect and call.call_id in context.executed_results:
            return context.executed_results[call.call_id]

        try:
            result = definition.handler(context, call.arguments)
        except Exception:
            result = _error("TOOL_EXECUTION_FAILED")
        if not isinstance(result, ToolResult):
            result = _error("TOOL_EXECUTION_FAILED")
        if definition.side_effect:
            context.executed_results[call.call_id] = result
        return result

    @staticmethod
    def _arguments_match_schema(schema: Mapping[str, Any], arguments: Any) -> bool:
        if not isinstance(arguments, dict) or schema.get("type", "object") != "object":
            return False
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            return False
        if any(key not in properties for key in arguments):
            return False
        if any(key not in arguments for key in required):
            return False
        return all(
            _value_matches_schema(arguments[key], property_schema)
            for key, property_schema in properties.items()
            if key in arguments
        )


def build_feynman_tool_registry(
    *,
    buggy_code_generator: Optional[BuggyCodeGenerator] = None,
    fix_evaluator: Optional[FixEvaluator] = None,
) -> ToolRegistry:
    generator = buggy_code_generator or _default_buggy_code_generator
    evaluator = fix_evaluator or _default_fix_evaluator
    registry = ToolRegistry()
    both_roles = frozenset({AgentRole.TEACHER_AGENT, AgentRole.STUDENT_AGENT})
    teacher_only = frozenset({AgentRole.TEACHER_AGENT})
    student_only = frozenset({AgentRole.STUDENT_AGENT})

    registry.register(ToolDefinition(
        "inspect_learning_state", "Inspect the current public learning state.",
        _object_schema(), both_roles, _inspect_learning_state,
    ))
    registry.register(ToolDefinition(
        "recall_memory", "Recall messages visible to the current role.",
        _object_schema(), both_roles, _recall_memory,
    ))
    registry.register(ToolDefinition(
        "record_learning_evidence", "Record concrete evidence of learning.",
        _object_schema(
            properties={
                "concept": _string_schema(MAX_CONCEPT_CHARS),
                "evidence": _string_schema(MAX_EVIDENCE_CHARS),
            },
            required=["concept", "evidence"],
        ), both_roles, _record_learning_evidence, side_effect=True,
    ))
    registry.register(ToolDefinition(
        "request_student_probe", "Request one bounded student probe intervention.",
        _object_schema(
            properties={
                "concept": _string_schema(MAX_CONCEPT_CHARS),
                "dimension": _string_schema(MAX_PROBE_DIMENSION_CHARS),
                "goal": _string_schema(MAX_GOAL_CHARS),
            },
            required=["concept", "dimension", "goal"],
        ), teacher_only, _request_student_probe, side_effect=True,
    ))
    registry.register(ToolDefinition(
        "ask_student_probe", "Ask the user one bounded probe question.",
        _object_schema(
            properties={"question": _string_schema(MAX_PROBE_QUESTION_CHARS)},
            required=["question"],
        ), student_only, _ask_student_probe, side_effect=True,
    ))
    registry.register(ToolDefinition(
        "assess_teaching_progress", "Assess learning coverage from the current student explanation.",
        _object_schema(
            properties={
                "assessment": _string_schema(32),
                "evidence": _string_schema(MAX_EVIDENCE_CHARS),
            },
            required=["assessment", "evidence"],
        ), student_only, _assess_teaching_progress, side_effect=True,
    ))
    registry.register(ToolDefinition(
        "generate_buggy_attempt", "Generate a student code attempt for review.",
        _object_schema(), student_only, _generate_buggy_attempt(generator), side_effect=True,
    ))
    registry.register(ToolDefinition(
        "evaluate_fix", "Evaluate a submitted code fix.",
        _object_schema(
            properties={"fixed_code": _string_schema(MAX_FIXED_CODE_CHARS)},
            required=["fixed_code"],
        ), student_only, _evaluate_fix(evaluator), side_effect=True,
    ))
    registry.register(ToolDefinition(
        "complete_goal", "Complete the goal after server-side readiness checks.",
        _object_schema(), both_roles, _complete_goal, side_effect=True,
    ))
    return registry


def _object_schema(
    *, properties: Optional[Dict[str, Any]] = None, required: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {"type": "object", "properties": properties or {}, "required": required or []}


def _string_schema(maximum: int) -> Dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": maximum}


def _value_matches_schema(value: Any, schema: Any) -> bool:
    if not isinstance(schema, Mapping):
        return False
    if schema.get("type") != "string" or not isinstance(value, str):
        return False
    minimum = schema.get("minLength", 0)
    maximum = schema.get("maxLength")
    return len(value) >= minimum and (maximum is None or len(value) <= maximum)


def _inspect_learning_state(context: ToolContext, _: Dict[str, Any]) -> ToolResult:
    state = context.memory.state
    content = {
        "phase": state.phase,
        "key_concepts": list(context.key_concepts),
        "learning_evidence": list(state.learning_evidence),
    }
    return ToolResult(ok=True, model_content=content, public_content=content)


def _recall_memory(context: ToolContext, _: Dict[str, Any]) -> ToolResult:
    messages = list(context.memory.visible_messages.get(context.role, []))[-10:]
    content = {"messages": messages}
    return ToolResult(ok=True, model_content=content, public_content=content)


def _record_learning_evidence(context: ToolContext, arguments: Dict[str, Any]) -> ToolResult:
    evidence = {"concept": arguments["concept"], "evidence": arguments["evidence"]}
    if (
        evidence["concept"] not in _allowed_concepts(context)
        or not _is_meaningful_evidence(evidence["evidence"])
    ):
        return _error("INVALID_LEARNING_EVIDENCE")
    all_evidence = [*context.memory.state.learning_evidence, evidence]
    return ToolResult(
        ok=True,
        model_content={"recorded": evidence},
        public_content={"recorded": evidence},
        state_patch={"learning_evidence": all_evidence},
        memory_events=[{"event_type": "learning_evidence", "metadata": {"evidence": evidence}}],
    )


def _request_student_probe(context: ToolContext, arguments: Dict[str, Any]) -> ToolResult:
    concept = arguments["concept"].strip()
    dimension = arguments["dimension"].strip()
    goal = arguments["goal"].strip()
    if concept not in _allowed_concepts(context):
        return _error("INVALID_STUDENT_PROBE")
    if dimension not in context.coverage_config.probe_dimensions:
        return _error("INVALID_STUDENT_PROBE")
    if not goal:
        return _error("INVALID_STUDENT_PROBE")
    return ToolResult(
        ok=True,
        model_content={"accepted": True},
        internal_content={
            "concept": concept,
            "dimension": dimension,
            "goal": goal,
        },
        signal_type="student_probe",
    )


def _ask_student_probe(context: ToolContext, arguments: Dict[str, Any]) -> ToolResult:
    target = _current_probe_target(context)
    question = arguments["question"].strip()
    if target is None or not _is_valid_probe_question(question):
        return _error("INVALID_STUDENT_PROBE")
    return ToolResult(
        ok=True,
        model_content={"accepted": True},
        public_content={"message": question},
        state_patch={"pending_probe": target},
    )


def _assess_teaching_progress(context: ToolContext, arguments: Dict[str, Any]) -> ToolResult:
    target = _current_probe_target(context)
    if target is None:
        return _error("INVALID_TEACHING_ASSESSMENT")
    try:
        decision = apply_coverage_assessment(
            context.memory.state,
            context.key_concepts,
            config=context.coverage_config,
            concept=target["concept"],
            dimension=target["dimension"],
            assessment=arguments["assessment"],
            evidence=arguments["evidence"],
            event_id=context.request_id,
        )
    except ValueError:
        return _error("INVALID_TEACHING_ASSESSMENT")
    return ToolResult(
        ok=True,
        model_content={
            "concept_status": decision.concept_status,
            "attempts": decision.attempts,
            "next_concept": decision.next_concept,
            "next_dimension": decision.next_dimension,
            "ready_for_code": decision.ready_for_code,
            "coverage_score": decision.coverage_score,
        },
        state_patch=decision.state_patch,
    )


def _generate_buggy_attempt(generator: BuggyCodeGenerator) -> ToolHandler:
    def handler(context: ToolContext, _: Dict[str, Any]) -> ToolResult:
        try:
            generated = generator(context)
        except Exception:
            return _error("BUGGY_ATTEMPT_FAILED", retryable=True)
        if not isinstance(generated, Mapping):
            return _error("BUGGY_ATTEMPT_FAILED", retryable=True)
        buggy_code = generated.get("buggy_code")
        message = generated.get("message", "")
        bugs = generated.get("bugs", [])
        if not isinstance(buggy_code, str) or not isinstance(message, str) or not isinstance(bugs, list):
            return _error("BUGGY_ATTEMPT_FAILED", retryable=True)
        if not _generated_code_is_safe(context, buggy_code, bugs):
            return _error("BUGGY_ATTEMPT_INVALID")
        visible = {"buggy_code": buggy_code, "message": _SAFE_CODE_REVIEW_MESSAGE}
        return ToolResult(
            ok=True,
            model_content=dict(visible),
            public_content={**visible, "ui_action": "show_code_review"},
            state_patch={"phase": "code_review", "code_review_status": "pending"},
            memory_events=[{
                "event_type": "buggy_attempt",
                "content": message,
                "metadata": {"artifact": {"buggy_code": buggy_code, "bugs": bugs}},
            }],
        )
    return handler


def _evaluate_fix(evaluator: FixEvaluator) -> ToolHandler:
    def handler(context: ToolContext, arguments: Dict[str, Any]) -> ToolResult:
        if not _fix_evaluation_is_ready(context):
            return _error("FIX_NOT_READY")
        try:
            evaluation = evaluator(context, arguments["fixed_code"])
        except Exception:
            return _error("FIX_EVALUATION_FAILED", retryable=True)
        correct, _ = _evaluation_fields(evaluation)
        if correct is None:
            return _error("FIX_EVALUATION_FAILED", retryable=True)
        content = {
            "correct": correct,
            "feedback": _SAFE_PASSED_FEEDBACK if correct else _SAFE_FAILED_FEEDBACK,
        }
        patch = {"code_review_status": "passed" if correct else "failed"}
        return ToolResult(ok=True, model_content=content, public_content=content, state_patch=patch)
    return handler


def _evaluation_fields(evaluation: Any) -> tuple[Optional[bool], str]:
    if isinstance(evaluation, Mapping):
        correct = evaluation.get("correct")
        feedback = evaluation.get("feedback", "")
    elif isinstance(evaluation, tuple) and len(evaluation) >= 2:
        correct, feedback = evaluation[0], evaluation[1]
    else:
        return None, ""
    return (correct, str(feedback)) if isinstance(correct, bool) else (None, "")


def _allowed_concepts(context: ToolContext) -> frozenset[str]:
    return frozenset(
        concept.strip()
        for concept in context.key_concepts
        if isinstance(concept, str) and concept.strip()
    )


def _is_meaningful_evidence(value: str) -> bool:
    text = value.strip()
    if len(text) < 5:
        return False
    normalized = text.casefold()
    return normalized not in {"none", "n/a", "不知道", "无", "没有"}


def _generated_code_is_safe(context: ToolContext, buggy_code: str, bugs: List[Any]) -> bool:
    reference_code = context.reference_code.strip()
    if not buggy_code.strip() or not bugs or not all(_structured_bug(bug) for bug in bugs):
        return False
    if reference_code and _semantic_code_key(buggy_code) == _semantic_code_key(reference_code):
        return False
    return not any(
        sensitive in buggy_code
        for sensitive in _internal_artifact_strings(bugs)
    )


def _current_probe_target(context: ToolContext) -> Optional[Dict[str, str]]:
    for candidate in (context.trigger, getattr(context.memory.state, "pending_probe", None)):
        if not isinstance(candidate, Mapping):
            continue
        concept = candidate.get("concept")
        dimension = candidate.get("dimension")
        if isinstance(concept, str) and concept.strip() and isinstance(dimension, str) and dimension.strip():
            return {"concept": concept.strip(), "dimension": dimension.strip()}
    return None


def _is_valid_probe_question(question: str) -> bool:
    if not question:
        return False
    if any(pattern.search(question) for pattern in _SELF_CONFIRMING_PROBE_PATTERNS):
        return False
    return any(pattern.search(question) for pattern in _QUESTION_HINT_PATTERNS)


def _structured_bug(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    description = value.get("description")
    anchors = (
        value.get("fix"),
        value.get("correct_version"),
        value.get("line"),
        value.get("line_hint"),
    )
    return (
        isinstance(description, str)
        and bool(description.strip())
        and any(anchor is not None and str(anchor).strip() for anchor in anchors)
    )


def _semantic_code_key(value: str) -> str:
    without_comments = re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", "", value)
    return re.sub(r"\s+", "", without_comments).casefold()


def _internal_artifact_strings(value: Any) -> List[str]:
    if isinstance(value, Mapping):
        return [item for nested in value.values() for item in _internal_artifact_strings(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _internal_artifact_strings(nested)]
    return [value] if isinstance(value, str) and len(value) >= 8 else []


def _complete_goal(context: ToolContext, _: Dict[str, Any]) -> ToolResult:
    state = context.memory.state
    if (
        not _base_completion_is_ready(context)
        or state.code_review_status not in {"passed", "approved", "complete"}
    ):
        return _error("GOAL_NOT_READY")
    return ToolResult(
        ok=True,
        model_content={"goal_status": "complete"},
        public_content={"goal_status": "complete"},
        state_patch={"status": "complete"},
    )


def _fix_evaluation_is_ready(context: ToolContext) -> bool:
    return (
        _base_completion_is_ready(context)
        and _latest_buggy_artifact(context) is not None
    )


def _base_completion_is_ready(context: ToolContext) -> bool:
    state = context.memory.state
    return state.phase == "code_review" and bool(state.learning_evidence)


def _default_buggy_code_generator(context: ToolContext) -> Mapping[str, Any]:
    from utils.thinking_ai import student_agent_write_code

    messages = context.memory.visible_messages.get(AgentRole.STUDENT_AGENT, [])
    return student_agent_write_code(
        context.assignment_title,
        list(context.key_concepts),
        context.reference_code,
        messages,
    )


def _default_fix_evaluator(context: ToolContext, fixed_code: str) -> Dict[str, Any]:
    from utils.thinking_ai import evaluate_feynman_code_fix

    artifact = _latest_buggy_artifact(context)
    if artifact is None:
        raise ValueError("missing buggy attempt")
    correct, feedback = evaluate_feynman_code_fix(
        artifact["buggy_code"], fixed_code, artifact["bugs"], context.reference_code,
    )
    if correct and not _deterministic_fix_confirms(
        artifact["buggy_code"], fixed_code, artifact["bugs"], context.reference_code,
    ):
        correct = False
        feedback = "修复尚未通过确定性检查。"
    return {"correct": correct, "feedback": feedback}


def _deterministic_fix_confirms(
    buggy_code: str,
    fixed_code: str,
    bugs: List[Any],
    reference_code: str,
) -> bool:
    fixed_key = _semantic_code_key(fixed_code)
    if not fixed_key or fixed_key == _semantic_code_key(buggy_code):
        return False
    reference_key = _semantic_code_key(reference_code)
    if reference_key and fixed_key == reference_key:
        return True
    compact_fixed = re.sub(r"\s+", "", fixed_code).casefold()
    for bug in bugs:
        if not isinstance(bug, Mapping):
            return False
        corrections = [
            str(bug.get(name) or "").strip()
            for name in ("correct_version", "fix")
        ]
        corrections = [item for item in corrections if item]
        if not corrections or not any(
            re.sub(r"\s+", "", item).casefold() in compact_fixed
            for item in corrections
        ):
            return False
    return True


def _latest_buggy_artifact(context: ToolContext) -> Optional[Dict[str, Any]]:
    for item in reversed(list(context.memory.code_artifact_index.values())):
        artifact = item.get("artifact") if isinstance(item, Mapping) else None
        if not isinstance(artifact, Mapping):
            continue
        buggy_code = artifact.get("buggy_code")
        bugs = artifact.get("bugs")
        if isinstance(buggy_code, str) and isinstance(bugs, list):
            return {"buggy_code": buggy_code, "bugs": bugs}
    return None


def _error(code: str, *, retryable: bool = False) -> ToolResult:
    return ToolResult(ok=False, error_code=code, retryable=retryable)
