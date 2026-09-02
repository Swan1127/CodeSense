"""Deterministic intent recognition for the Stage 3 public forum.

Intent recognition is deliberately local and bounded.  It decides which
agent should receive the learner's newest message without making another LLM
request.  The selected agent still performs the only model call for the
current forum turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contracts import AgentRole


INTENT_ASK_TEACHER = "ask_teacher"
INTENT_ASK_STUDENT = "ask_student"
INTENT_ANSWER_TEACHER = "answer_teacher"
INTENT_ANSWER_STUDENT = "answer_student"
INTENT_EXPLAIN_CONCEPT = "explain_concept"
INTENT_CONTINUE = "continue_learning"
INTENT_AMBIGUOUS = "ambiguous"


_TEACHER_DIRECT_CUES = (
    "老师",
    "教师",
    "teacher agent",
    "teacher_agent",
)
_STUDENT_DIRECT_CUES = (
    "小明",
    "同学",
    "同伴",
    "student agent",
    "student_agent",
)
_TEACHER_CONTENT_CUES = (
    "讲解",
    "解释",
    "为什么",
    "为何",
    "原理",
    "定义",
    "含义",
    "概念",
    "区别",
    "怎么写",
    "如何写",
    "怎么实现",
    "如何实现",
    "代码",
    "报错",
    "bug",
    "错误",
    "修复",
    "编译",
    "运行",
)
_STUDENT_CONTENT_CUES = (
    "场景",
    "例子",
    "实例",
    "案例",
    "应用",
    "用法",
    "不会用",
    "不太懂",
    "不懂",
    "不清楚",
    "不知道",
    "具体怎么用",
    "实际怎么",
)
_ANSWER_CUES = (
    "因为",
    "所以",
    "应该",
    "输出",
    "循环",
    "变量",
    "边界",
    "如果",
    "等于",
    "执行",
    "索引",
    "输入",
    "返回",
    "会在",
    "意味着",
    "表示",
    "我的理解",
    "我理解",
    "我认为",
    "我会",
    "我懂",
    "我明白",
    "不懂",
    "不清楚",
    "不知道",
    "想明白",
    "回应",
    "回答",
)
_CONTINUE_CUES = (
    "继续",
    "下一步",
    "接着",
    "好的",
    "好吧",
    "嗯",
    "明白了",
)


@dataclass(frozen=True)
class ForumIntent:
    """The safe, model-independent result of recognizing one user message."""

    name: str
    target_role: Optional[AgentRole] = None
    confidence: float = 0.0
    reason: str = ""
    is_question: bool = False
    is_answer: bool = False


@dataclass(frozen=True)
class ForumRouting:
    """Public-safe explanation of the final one-speaker routing decision."""

    intent: ForumIntent
    selected_role: AgentRole
    selection_source: str

    def to_public_dict(self) -> dict:
        return {
            "intent": self.intent.name,
            "confidence": round(max(0.0, min(1.0, float(self.intent.confidence))), 2),
            "target_role": self.selected_role.value,
            "selection_source": self.selection_source,
            "reason": self.intent.reason,
            "is_question": self.intent.is_question,
            "is_answer": self.intent.is_answer,
        }


def recognize_forum_intent(
    message: str,
    *,
    reply_source_role: AgentRole | str | None = None,
    last_agent_role: AgentRole | str | None = None,
    has_student_probe: bool = False,
    has_student_intent: bool = False,
    phase: str = "student_dialogue",
) -> ForumIntent:
    """Recognize the learner's conversational intent.

    Precedence is intentionally explicit:

    1. Direct addressees ("老师" / "小明") win.
    2. A server-authorized Student probe or an explicit reply context tells us
       whose question the learner is answering.
    3. Teacher- and Student-oriented content cues route new questions.
    4. A plain explanation is left to the existing fairness/probability
       scheduler, so intent recognition never creates a second speaker.

    ``phase`` is accepted so callers can keep one routing API across Stage 3;
    code review itself remains handled by the dedicated code-review endpoint.
    """
    text = str(message or "").strip()
    if not text:
        return ForumIntent(INTENT_AMBIGUOUS, confidence=0.0, reason="empty_message")

    question = _looks_like_question(text)
    answer = _looks_like_answer(text)
    teacher_direct = _contains_any(text, _TEACHER_DIRECT_CUES)
    student_direct = _contains_any(text, _STUDENT_DIRECT_CUES)

    # Directly addressing a role is the clearest semantic signal.  It also
    # lets "老师，给我一个例子" remain a Teacher turn instead of being
    # misclassified by the word "例子".
    if teacher_direct:
        return ForumIntent(
            INTENT_ASK_TEACHER,
            AgentRole.TEACHER_AGENT,
            0.99,
            "direct_teacher_address",
            question,
            answer,
        )
    if student_direct:
        intent_name = INTENT_ANSWER_STUDENT if answer and not question else INTENT_ASK_STUDENT
        return ForumIntent(
            intent_name,
            AgentRole.STUDENT_AGENT,
            0.98,
            "direct_student_address",
            question,
            answer,
        )

    student_context = bool(has_student_probe or has_student_intent)
    if student_context:
        # The server has already authorized a Student probe.  The newest
        # learner message is therefore the current answer, not an old queued
        # response.  Even a short "好的" should go to that Student question.
        return ForumIntent(
            INTENT_ASK_STUDENT if question else INTENT_ANSWER_STUDENT,
            AgentRole.STUDENT_AGENT,
            0.96,
            "pending_student_probe",
            question,
            answer,
        )

    context_role = _coerce_agent_role(reply_source_role) or _coerce_agent_role(last_agent_role)
    if context_role is AgentRole.STUDENT_AGENT and text:
        return ForumIntent(
            INTENT_ASK_STUDENT if question else INTENT_ANSWER_STUDENT,
            AgentRole.STUDENT_AGENT,
            0.91,
            "reply_to_student_context",
            question,
            answer,
        )
    if context_role is AgentRole.TEACHER_AGENT and answer and not question:
        return ForumIntent(
            INTENT_ANSWER_TEACHER,
            AgentRole.TEACHER_AGENT,
            0.91,
            "reply_to_teacher_context",
            question,
            answer,
        )

    teacher_content = _contains_any(text, _TEACHER_CONTENT_CUES)
    student_content = _contains_any(text, _STUDENT_CONTENT_CUES)
    if teacher_content:
        return ForumIntent(
            INTENT_ASK_TEACHER,
            AgentRole.TEACHER_AGENT,
            0.88,
            "teacher_content_signal",
            question,
            answer,
        )
    if student_content:
        return ForumIntent(
            INTENT_ASK_STUDENT,
            AgentRole.STUDENT_AGENT,
            0.88,
            "student_content_signal",
            question,
            answer,
        )

    if answer or _contains_any(text, _ANSWER_CUES):
        return ForumIntent(
            INTENT_EXPLAIN_CONCEPT,
            confidence=0.62,
            reason="concept_explanation_without_addressee",
            is_question=question,
            is_answer=answer,
        )
    if _contains_any(text, _CONTINUE_CUES):
        return ForumIntent(
            INTENT_CONTINUE,
            confidence=0.45,
            reason="short_continuation",
            is_question=question,
            is_answer=answer,
        )
    return ForumIntent(
        INTENT_AMBIGUOUS,
        confidence=0.2,
        reason="no_stable_signal",
        is_question=question,
        is_answer=answer,
    )


def _coerce_agent_role(value: AgentRole | str | None) -> Optional[AgentRole]:
    if isinstance(value, AgentRole):
        return value
    try:
        return AgentRole(str(value)) if value is not None else None
    except ValueError:
        return None


def _contains_any(text: str, cues: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(cue.casefold() in lowered for cue in cues)


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    if "?" in stripped or "？" in stripped:
        return True
    if stripped.endswith(("吗", "呢")):
        return True
    return stripped.startswith((
        "为什么",
        "为何",
        "怎么",
        "如何",
        "什么",
        "哪",
        "请问",
        "能否",
        "能不能",
        "可不可以",
    ))


def _looks_like_answer(text: str) -> bool:
    if _looks_like_question(text):
        return False
    return _contains_any(text, _ANSWER_CUES)


__all__ = [
    "ForumIntent",
    "ForumRouting",
    "INTENT_AMBIGUOUS",
    "INTENT_ANSWER_STUDENT",
    "INTENT_ANSWER_TEACHER",
    "INTENT_ASK_STUDENT",
    "INTENT_ASK_TEACHER",
    "INTENT_CONTINUE",
    "INTENT_EXPLAIN_CONCEPT",
    "recognize_forum_intent",
]
