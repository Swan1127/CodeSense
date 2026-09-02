import pytest

from utils.agents.contracts import AgentRole
from utils.agents.intent import (
    INTENT_ANSWER_STUDENT,
    INTENT_ANSWER_TEACHER,
    INTENT_ASK_STUDENT,
    INTENT_ASK_TEACHER,
    INTENT_CONTINUE,
    INTENT_EXPLAIN_CONCEPT,
    recognize_forum_intent,
)


@pytest.mark.parametrize(
    ("message", "intent_name", "role"),
    [
        ("老师，给我一个循环边界的例子。", INTENT_ASK_TEACHER, AgentRole.TEACHER_AGENT),
        ("小明，我还是不会把它用到实际场景里。", INTENT_ASK_STUDENT, AgentRole.STUDENT_AGENT),
    ],
)
def test_direct_addressee_wins_over_content_cues(message, intent_name, role):
    intent = recognize_forum_intent(message)

    assert intent.name == intent_name
    assert intent.target_role is role
    assert intent.reason in {"direct_teacher_address", "direct_student_address"}


def test_pending_student_probe_routes_the_newest_answer_to_student():
    intent = recognize_forum_intent(
        "应该输出 0，因为前 0 项为空。",
        has_student_probe=True,
    )

    assert intent.name == INTENT_ANSWER_STUDENT
    assert intent.target_role is AgentRole.STUDENT_AGENT
    assert intent.reason == "pending_student_probe"


def test_reply_context_distinguishes_teacher_and_student_answers():
    teacher_intent = recognize_forum_intent(
        "应该输出 0，因为这是第一项。",
        last_agent_role=AgentRole.TEACHER_AGENT,
    )
    student_intent = recognize_forum_intent(
        "应该输出 0，因为这是第一项。",
        reply_source_role=AgentRole.STUDENT_AGENT,
    )

    assert teacher_intent.name == INTENT_ANSWER_TEACHER
    assert teacher_intent.target_role is AgentRole.TEACHER_AGENT
    assert student_intent.name == INTENT_ANSWER_STUDENT
    assert student_intent.target_role is AgentRole.STUDENT_AGENT


def test_teacher_addressee_is_not_overridden_by_student_example_word():
    intent = recognize_forum_intent("老师，请用一个真实场景解释循环边界。")

    assert intent.name == INTENT_ASK_TEACHER
    assert intent.target_role is AgentRole.TEACHER_AGENT


def test_plain_explanation_and_short_continuation_are_scheduler_fallbacks():
    explanation = recognize_forum_intent("我已经理解循环边界了。")
    continuation = recognize_forum_intent("继续。")

    assert explanation.name == INTENT_EXPLAIN_CONCEPT
    assert explanation.target_role is None
    assert continuation.name == INTENT_CONTINUE
    assert continuation.target_role is None
