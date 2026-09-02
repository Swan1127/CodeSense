import pytest

from utils import thinking_ai


def test_structured_stage1_answers_use_local_fast_evaluation(monkeypatch):
    description = (
        "【问题 1】：如果 N 等于 0，程序应该输出什么？\n"
        "【回答】：N=0 时没有要输出的项，所以结果为空。\n\n"
        "【问题 2】：循环从第几项开始，为什么？\n"
        "【回答】：前两项是 0 和 1，循环从第三项开始，后面的项由前两项相加得到。\n\n"
        "【问题 3】：如何保证输出顺序与数列顺序一致？\n"
        "【回答】：按下标顺序保存每一项，最后按原顺序输出结果。"
    )

    class UnexpectedLLMCall:
        def __init__(self):
            pytest.fail("结构化阶段一回答不应调用远程 AI 评判")

    monkeypatch.setattr(thinking_ai, "SharedLLMClient", UnexpectedLLMCall)

    score, feedback = thinking_ai.evaluate_description(
        description,
        [
            "先读入 N，并明确需要输出前 N 项斐波那契数列。",
            "用两个变量保存相邻的两个数，循环中根据前两项得到下一项。",
            "每次得到新项后更新两个变量并输出，注意 N 为 0 或 1 的边界。",
        ],
        "循环与斐波那契数列",
    )

    assert score >= 50
    assert "快速检查完成" in feedback


def test_unstructured_stage1_answers_keep_ai_fallback(monkeypatch):
    class FakeLLM:
        def is_available(self):
            return True

        def chat(self, messages, **kwargs):
            return '{"score": 63, "feedback": "方向基本正确"}'

    monkeypatch.setattr(thinking_ai, "SharedLLMClient", FakeLLM)

    score, feedback = thinking_ai.evaluate_description(
        "我会按照题目要求完成程序。",
        ["先读取输入", "完成核心处理", "输出结果"],
        "普通编程题",
    )

    assert score == 63
    assert feedback == "方向基本正确"
