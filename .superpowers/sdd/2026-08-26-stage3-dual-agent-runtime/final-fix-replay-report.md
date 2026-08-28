# Stage3 replay 最终修复报告

日期：2026-08-28  
工作树：`E:\CodeSense\guided-learning-paper-revision`  
起始 HEAD：`c9132987dde1b288d4fdeffe10bb4e9b3994dfe0`

## 本轮修复内容

只处理 scoped review 剩下的一个 Important：`generate_buggy_attempt()` 在 side-effect `tool_result` 已成功持久化、但 `buggy_attempt` 内部事件缺失的崩溃窗口里，错误地把请求对外改判成 `BUGGY_ATTEMPT_FAILED`。

本轮改动保持在允许范围内：

- `tests/test_stage3_agent_loop.py`
- `utils/agents/feynman.py`
- `.superpowers/sdd/2026-08-26-stage3-dual-agent-runtime/final-fix-replay-report.md`

没有改 `memory.py`、`loop.py`、研究输出或其他无关文件。

## 根因

`AgentLoop` 在发现同一 `request_id + call_id` 已有成功 `tool_result` 时，会直接 replay 持久化结果，不再执行 side effect callback。这一层本身没问题。

问题出在 `DualFeynmanRuntime.generate_buggy_attempt()`。它在 `_run_forced_tool()` 成功后，没有把刚刚 replay 出来的 `tool_result.public_content` 当作对外成功事实，而是继续强制调用 `_artifact_for(request_id)` 查找 `buggy_attempt` 事件里的内部工件。只要进程恰好崩在“成功 `tool_result` 已写入，但 `buggy_attempt` 还没来得及写”这个窗口，对外结果就会变成 `BUGGY_ATTEMPT_FAILED`，同时底层又已经有成功终态，状态因此分裂。

## 最小修复

`generate_buggy_attempt()` 现在优先从已持久化成功 `tool_result.public_content` 恢复公开结果：

- 如果 `public_content.buggy_code` 存在，就直接返回 `show_code_review`、`buggy_code` 和公开 `message`。
- 只有当公开结果里拿不到 `buggy_code` 时，才回退到旧的内部 artifact 路径。
- 整个恢复过程不会重跑 callback，也不会补写新的 `buggy_attempt` 事件。

这满足当前 finding 的目标：成功 replay 时先恢复安全公开结果；如果内部 artifact 另有保存，现有 MemoryStore 会继续索引它；如果没有，则内部信息保持缺失，后续修复评估会安全失败，而不是重新执行副作用。

## TDD 记录

先加一条只覆盖崩溃窗口的回归测试，然后先看红，再看绿。

### Red

命令：

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_replayed_buggy_tool_result_without_artifact_recovers_public_result -q --disable-warnings
```

结果：

```text
FAILED tests/test_stage3_agent_loop.py::test_replayed_buggy_tool_result_without_artifact_recovers_public_result
E       AssertionError: assert False is True
E        +  where False = AgentResult(... error_code='BUGGY_ATTEMPT_FAILED').success
```

测试预置了同一 `request_id` 的 side-effect `tool_call` claim 和成功 `tool_result`，故意不写 `buggy_attempt`。实际结果正是报告描述的失败形态。

### Green

命令：

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py::test_replayed_buggy_tool_result_without_artifact_recovers_public_result -q --disable-warnings
```

结果：

```text
1 passed in 0.35s
```

新测试同时确认：

- 不重新执行 `buggy_code_generator`
- 不新增 `buggy_attempt` 事件
- 返回 `show_code_review`
- 返回持久化的 `buggy_code` 和公开 `message`

## 最终验证

Stage3 focused suite：

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py tests/test_stage3_agent_memory.py tests/test_stage3_agent_tools.py tests/test_stage3_agent_loop.py tests/test_stage3_agent_routes.py -q --disable-warnings
```

结果：

```text
116 passed, 205375 warnings in 26.72s
```

全量测试：

```powershell
& 'E:\anaconda\python.exe' -m pytest tests -q
```

结果：

```text
471 passed, 450207 warnings in 68.51s
```

前端语法检查：

```powershell
& 'E:\nodejs\node.exe' --check static/js/thinking.js
```

结果：`exit 0`

## Remaining limitations

1. 这次修复只恢复对外公开成功结果，不会凭空补全缺失的内部 `buggy_attempt` artifact。
2. 如果某次历史记录里只有安全 `public_content`，没有任何内部 artifact 元数据，那么后续 `evaluate_fix()` 仍会因为拿不到隐藏 bug 而安全失败。这是刻意保守的行为，避免为了“补全”结果去重跑副作用。
3. 本轮没有扩大到更高阶的原子持久化改造，也没有调整 scoped 外文件。
