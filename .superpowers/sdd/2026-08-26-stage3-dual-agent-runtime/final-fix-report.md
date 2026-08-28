# Stage 3 双智能体运行时最终修复报告

日期：2026-08-28
基线 HEAD：`fc061236d90e7e744012b0de4417f0bb3c789492`

## 结果

C1-C3、I1-I6、M1-M2 已在限定文件范围内修复。没有修改 `models.py`，也没有新增表、字段或迁移。Student/public 投影仍不包含标准答案、隐藏 Bug 或正确修复；完整工件只保存在内部事件中。

接手时工作树已经有一组未提交的 C1/C2 与部分 C3 修复草稿，涉及 `routes/thinking.py`、`utils/agents/{tools,loop,memory,feynman}.py` 和两份 Stage3 测试。首次 focused 运行的真实结果是 `8 failed, 86 passed`；C1/C2 的既有用例当时已绿，因此本报告不把它们记成由本轮亲自观察到的 red。

## Finding 处理情况

- C1：`generate_buggy_attempt` 成功后由服务端写入 `phase=code_review`、`show_code_review` 和公开 `buggy_code`；`evaluate_fix(correct=True)` 也会在当前模型决策中直接形成终态，不再多走一次模型调用。AgentLoop 按工具名和受校验结果判定终态。Teacher/Student 均注册 `complete_goal`，授权由统一 readiness gate 决定。前端收到 Student 响应中的 `buggy_code` 后直接展示，不再调用一次 `write_code`。
- C2：四个 Stage3 端点统一要求会话归属当前用户、`current_stage == 3`、`stage2_completed`、`status == in_progress`。`complete_session` 只在已存在 `validated=true` 的 `stage_pass` 且会话已经完成时保存计时，不能授予完成。修复评估还要求 code-review 阶段、学习证据和内部错误工件齐全。
- C3：配置 `SESSION_REDIS` 时使用 `stage3-agent-session:<id>` 的 120 秒 TTL 锁，阻塞上限 5 秒；测试环境或无 Redis 时保留进程内锁。副作用回调前持久化 claim；已有 `tool_result` 时重放，只有 claim 没有结果时返回 `TOOL_CALL_UNFINISHED`，不重复执行。终态消息和 terminal state snapshot 在一次 `append_many` 中提交。
- I1：普通 Agent 文本在写 `agent_decision`、`agent_message` 和 API 响应前统一经过 `sanitize_response`，随后按角色 `max_output_chars` 截断。代码审查工件继续使用独立字段。
- I2：合同限制每个决策最多 4 个工具，`call_id` 最长 128 字符、工具名最长 80 字符；AgentLoop 再执行运行时校验，每请求最多 4 个工具，并在执行整批前拒绝超限。
- I3：只有 terminal `state_snapshot` 是新请求的成功幂等事实；旧 `agent_message`/旧失败事件仍可兼容恢复。重复正确评估会重放结果并修复 `ThinkingSession` 字段，不会再次调用评估器。
- I4：错误代码必须包含非空结构化 bugs，且去除注释和空白后必须与参考代码有实质差异。无 Key 或模型解析失败时使用确定性变异，不再回退为标准答案。评估 JSON 要求 `type(correct) is bool`；默认评估只有在 LLM 判断和确定性参考/修复片段检查同时通过时才返回正确。
- I5：唯一成功 chat 终态才递增 Teacher/Student rounds；重复、forced-tool 和失败请求不递增。快照会更新 `agent_id`、`turn_index`、`last_user_message`、`current_focus`、`last_decision`、`goal_status`，并幂等同步 `ThinkingSession.stage3_*_rounds`。
- I6：新增或修正真实注册表、真实 `DualFeynmanRuntime`、路由数据库恢复、Redis 锁、崩溃点重放、默认 callback 和输出过滤测试；原先依赖 `bugs=[]`、缺少学习证据却期望完成的测试 fixture 已改成真实可授权状态，没有降低断言。
- M1：模型异常、fallback error 和非法决策会写 `agent_decision_error`，只记录截断后的 request id、角色、step 和安全 error code。
- M2：事件存储和路由恢复统一按 `(created_at, id)` 排序，并对已取出的日志再做稳定排序。

## TDD 记录

首次基线：

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py tests/test_stage3_agent_memory.py tests/test_stage3_agent_tools.py tests/test_stage3_agent_loop.py tests/test_stage3_agent_routes.py -q
# 8 failed, 86 passed
```

本轮逐条观察到 red，再转 green 的测试如下。每条均使用同一命令先得到退出码 1，修改生产代码后再运行并得到退出码 0：

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_side_effect_tool_claim_is_persisted_before_callback_runs -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_unfinished_side_effect_claim_is_refused_without_reexecution -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_terminal_agent_message_and_snapshot_are_persisted_in_one_batch -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_duplicate_successful_fix_reconciles_session_without_re_evaluation -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_correct_fix_cannot_complete_without_learning_evidence -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py::test_agent_decision_rejects_oversized_tool_batches_and_identifiers -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_agent_loop_sanitizes_code_before_public_response_and_persistence -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_agent_loop_bounds_sanitized_response_before_persistence -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_agent_loop_rejects_oversized_tool_batch_before_executing_any_call -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_agent_loop_rejects_request_tool_limit_before_executing_next_batch -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_agent_loop_records_sanitized_agent_decision_error_event -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_routes.py::test_stage3_event_order_is_stable_for_equal_timestamps -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_unique_successful_chat_updates_rounds_and_agent_state_once -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_tools.py::test_buggy_attempt_requires_structured_nontrivial_mutation -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_tools.py::test_default_fix_evaluator_requires_deterministic_bug_elimination -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_tools.py::test_no_key_buggy_code_fallback_is_never_the_reference -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_tools.py::test_default_evaluator_rejects_string_boolean -q --disable-warnings
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_correct_evaluate_fix_is_terminal_without_second_model_step -q
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception -q
```

工具上限测试第一次因 `FakeRegistry` 缺少生产接口 `is_side_effect()` 而报错；补齐测试替身后重新运行，确认实际 red 是未限流导致执行完工具后返回 `MODEL_ERROR`，再实现限流。

## 最终验证

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py tests/test_stage3_agent_memory.py tests/test_stage3_agent_tools.py tests/test_stage3_agent_loop.py tests/test_stage3_agent_routes.py -q --disable-warnings
# 115 passed, 205375 warnings in 23.64s

& 'E:\nodejs\node.exe' --check static/js/thinking.js
# exit 0

& 'E:\anaconda\python.exe' -m pytest tests -q
# 470 passed, 450215 warnings in 70.04s

git diff --check
# exit 0
```

warning 主要来自当前 Werkzeug/SQLAlchemy/Flask-Session 版本的弃用提示；本轮没有把这些跨项目升级纳入 Stage3 修复。

## 修改文件

- `routes/thinking.py`
- `static/js/thinking.js`
- `utils/agents/contracts.py`
- `utils/agents/feynman.py`
- `utils/agents/loop.py`
- `utils/agents/memory.py`
- `utils/agents/tools.py`
- `utils/thinking_ai.py`
- `tests/test_stage3_agent_contracts.py`
- `tests/test_stage3_agent_loop.py`
- `tests/test_stage3_agent_routes.py`
- `tests/test_stage3_agent_tools.py`
- `.superpowers/sdd/2026-08-26-stage3-dual-agent-runtime/final-fix-report.md`

## 限制

1. 没有 Redis 时只能提供进程内互斥，不能声称 Gunicorn 多 worker 间互斥；生产跨进程保证依赖可用的 `SESSION_REDIS`。
2. 受“不改 models.py 表结构”约束，持久 claim 没有数据库唯一索引。Redis 锁负责跨 worker 串行；只有 claim 没有 result 的崩溃点采用安全拒绝重跑，需要后续人工或专门恢复流程处理。
3. 默认修复门禁采用严格布尔解析、规范化参考代码比较和记录修复片段匹配，没有引入编译沙箱或题目测试用例执行器。
4. 全量测试保留大量既有弃用 warning；它们不属于本轮 finding。

未解决 finding：无。以上限制是已批准“不改表结构”和当前基础设施下的明确边界。
