from dataclasses import replace

from research_eval.simulation.conditions import (
    SimulationState,
    StructuralAdapter,
)
from research_eval.simulation.framework_adapter import (
    FrameworkAdapter,
    ThinkingFunctions,
)
from research_eval.simulation.models import Condition, Persona, TaskCase
from research_eval.simulation.zhipu_roles import RoleResponse


def task():
    return TaskCase(
        task_id="T01",
        split="formal",
        topic="linear",
        difficulty="easy",
        title="链表测试",
        description="删除链表中的指定值。",
        key_steps=("建立虚拟头节点", "遍历并删除", "返回新头节点"),
        reference_code="int main(){return 0;}",
        quiz_steps=({"step_id": "s1", "correct_answer": "dummy.next=head;"},),
    )


def persona():
    return Persona(
        persona_id="P1",
        label="缺少计划",
        hidden_state="无计划",
        observable_behavior="回答零散",
        transition_rules=("P1_T1|形成目标",),
        forbidden_knowledge=("不能直接给完整代码",),
    )


class FakeRoleClient:
    def __init__(self):
        self.calls = []

    def complete(self, role, system_prompt, messages, temperature, max_tokens):
        self.calls.append((role, system_prompt, list(messages), temperature, max_tokens))
        return RoleResponse(
            role=role,
            content="system response",
            model="glm-4.5-flash",
            status_code=200,
            error_code="",
            retries=0,
            elapsed_seconds=0.01,
            timestamp_utc="2026-07-22T00:00:00+00:00",
        )


class FakeThinking:
    def __init__(self):
        self.calls = []

    def evaluate_description(self, description, key_steps, title):
        self.calls.append(("evaluate_description", description, tuple(key_steps), title))
        return 50.0, "还缺少关键步骤"

    def generate_stage1_hint(self, description, key_steps, title, hint_count):
        self.calls.append(("generate_stage1_hint", hint_count))
        return "阶段一提示"

    def generate_stage2_hint(self, description, current_ids, blocks, title, hint_count):
        self.calls.append(("generate_stage2_hint", tuple(current_ids), hint_count))
        return "阶段二提示"

    def teacher_agent_chat(self, messages, title, key_steps, description, **kwargs):
        self.calls.append(("teacher_agent_chat", list(messages), kwargs.get("student_state")))
        return "教师追问"

    def student_agent_chat(self, messages, title, key_steps, difficulty, **kwargs):
        self.calls.append(("student_agent_chat", list(messages), kwargs.get("student_state")))
        return "学生代理追问"

    def student_agent_write_code(self, title, key_steps, reference_code, messages):
        self.calls.append(("student_agent_write_code", list(messages)))
        return {
            "buggy_code": "int main(){return 1;}",
            "bugs": [{"line": 1, "description": "返回值错误", "fix": "改为0"}],
            "message": "请帮我修正",
        }

    def evaluate_feynman_code_fix(self, buggy_code, fixed_code, bugs, reference_code):
        self.calls.append(("evaluate_feynman_code_fix", fixed_code))
        return True, "修正正确"

    def bundle(self):
        return ThinkingFunctions(
            evaluate_description=self.evaluate_description,
            generate_stage1_hint=self.generate_stage1_hint,
            generate_stage2_hint=self.generate_stage2_hint,
            teacher_agent_chat=self.teacher_agent_chat,
            student_agent_chat=self.student_agent_chat,
            student_agent_write_code=self.student_agent_write_code,
            evaluate_feynman_code_fix=self.evaluate_feynman_code_fix,
        )


def make_state(condition):
    return SimulationState(task=task(), persona=persona(), condition=condition)


def run_until_complete(adapter, state, limit=8):
    for index in range(limit):
        step = adapter.respond(state, f"learner answer {index}")
        if step.completed:
            return step
    return step


def test_c0_calls_only_direct_role_prompt():
    role = FakeRoleClient()
    adapter = StructuralAdapter(Condition.C0, role, "direct", "fixed")
    state = make_state(Condition.C0)

    step = adapter.respond(state, "请直接告诉我")

    assert step.event_type == "direct_answer"
    assert len(role.calls) == 1
    assert role.calls[0][1] == "direct"


def test_c1_follows_fixed_stages_without_framework_evaluation():
    role = FakeRoleClient()
    adapter = StructuralAdapter(Condition.C1, role, "direct", "fixed")
    state = make_state(Condition.C1)

    stages = [adapter.respond(state, "answer").stage for _ in range(8)]

    assert stages == [1, 1, 2, 2, 3, 3, 3, 3]
    assert state.system_turns == 8


def test_c2_calls_full_framework_sequence():
    fake = FakeThinking()
    adapter = FrameworkAdapter(Condition.C2, fake.bundle())
    state = make_state(Condition.C2)

    final = run_until_complete(adapter, state)
    names = [row[0] for row in fake.calls]

    assert final.completed is True
    for expected in (
        "evaluate_description",
        "generate_stage1_hint",
        "generate_stage2_hint",
        "teacher_agent_chat",
        "student_agent_chat",
        "student_agent_write_code",
        "evaluate_feynman_code_fix",
    ):
        assert expected in names


def test_a1_retains_sequence_but_removes_adaptive_state():
    fake = FakeThinking()
    adapter = FrameworkAdapter(Condition.A1, fake.bundle())
    state = make_state(Condition.A1)
    state.history.append({"role": "user", "content": "private history"})
    state.hint_count = 5
    state.validation_result = {"score": 50}

    run_until_complete(adapter, state)

    teacher = next(row for row in fake.calls if row[0] == "teacher_agent_chat")
    student = next(row for row in fake.calls if row[0] == "student_agent_chat")
    stage1_hints = [row for row in fake.calls if row[0] == "generate_stage1_hint"]
    assert teacher[1] == [] and teacher[2] == {}
    assert student[1] == [] and student[2] == {}
    assert all(row[1] == 0 for row in stage1_hints)


def test_a2_skips_student_agent_dialogue():
    fake = FakeThinking()
    adapter = FrameworkAdapter(Condition.A2, fake.bundle())
    state = make_state(Condition.A2)

    run_until_complete(adapter, state)
    names = [row[0] for row in fake.calls]

    assert "student_agent_chat" not in names
    assert "student_agent_write_code" in names
    assert "evaluate_feynman_code_fix" in names


def test_a3_omits_code_generation_and_repair():
    fake = FakeThinking()
    adapter = FrameworkAdapter(Condition.A3, fake.bundle())
    state = make_state(Condition.A3)

    final = run_until_complete(adapter, state)
    names = [row[0] for row in fake.calls]

    assert final.completed is True
    assert state.code_repair_omitted is True
    assert "student_agent_chat" in names
    assert "student_agent_write_code" not in names
    assert "evaluate_feynman_code_fix" not in names


def test_a1_does_not_advance_early_from_evaluation_score():
    fake = FakeThinking()

    def high_score(description, key_steps, title):
        fake.calls.append(("evaluate_description", description, tuple(key_steps), title))
        return 95.0, "评分很高"

    functions = fake.bundle()
    functions = replace(functions, evaluate_description=high_score)
    adapter = FrameworkAdapter(Condition.A1, functions)
    state = make_state(Condition.A1)

    adapter.respond(state, "完整回答")

    assert state.stage == 1
