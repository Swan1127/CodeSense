"""Server-authoritative Stage 3 agent tools.

Tool schemas and permissions live here rather than in model prompts.  Handler
results deliberately keep private artifacts out of ``model_content``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional

from .contracts import AgentRole, ToolCall, ToolResult
from .memory import MemorySnapshot


MAX_CONCEPT_CHARS = 200
MAX_EVIDENCE_CHARS = 2_000
MAX_FIXED_CODE_CHARS = 8_000

ToolHandler = Callable[["ToolContext", Dict[str, Any]], ToolResult]
BuggyCodeGenerator = Callable[["ToolContext"], Mapping[str, Any]]
FixEvaluator = Callable[["ToolContext", str], Any]


@dataclass
class ToolContext:
    session_id: int
    request_id: str
    role: AgentRole
    memory: MemorySnapshot
    assignment_title: str = ""
    key_concepts: List[str] = field(default_factory=list)
    reference_code: str = ""
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
        ), teacher_only, _record_learning_evidence, side_effect=True,
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
        _object_schema(), teacher_only, _complete_goal, side_effect=True,
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
    all_evidence = [*context.memory.state.learning_evidence, evidence]
    return ToolResult(
        ok=True,
        model_content={"recorded": evidence},
        public_content={"recorded": evidence},
        state_patch={"learning_evidence": all_evidence},
        memory_events=[{"event_type": "learning_evidence", "metadata": {"evidence": evidence}}],
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
        visible = {"buggy_code": buggy_code, "message": message}
        return ToolResult(
            ok=True,
            model_content=dict(visible),
            public_content=dict(visible),
            memory_events=[{
                "event_type": "buggy_attempt",
                "content": message,
                "metadata": {"artifact": {"buggy_code": buggy_code, "bugs": bugs}},
            }],
        )
    return handler


def _evaluate_fix(evaluator: FixEvaluator) -> ToolHandler:
    def handler(context: ToolContext, arguments: Dict[str, Any]) -> ToolResult:
        try:
            evaluation = evaluator(context, arguments["fixed_code"])
        except Exception:
            return _error("FIX_EVALUATION_FAILED", retryable=True)
        correct, feedback = _evaluation_fields(evaluation)
        if correct is None:
            return _error("FIX_EVALUATION_FAILED", retryable=True)
        content = {"correct": correct, "feedback": feedback}
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


def _complete_goal(context: ToolContext, _: Dict[str, Any]) -> ToolResult:
    state = context.memory.state
    if (
        not state.learning_evidence
        or state.phase != "code_review"
        or state.code_review_status not in {"passed", "approved", "complete"}
    ):
        return _error("GOAL_NOT_READY")
    return ToolResult(
        ok=True,
        model_content={"goal_status": "complete"},
        public_content={"goal_status": "complete"},
        state_patch={"status": "complete"},
    )


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
    return {"correct": correct, "feedback": feedback}


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
