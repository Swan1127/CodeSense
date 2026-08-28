# 阶段三双智能体 AgentLoop 设计规格

日期：2026-08-24  
状态：设计评审通过，待规格自审和用户审阅  
范围：CodeSense 三阶段引导学习系统的阶段三费曼教学

## 1. 背景

阶段三目前有老师 Agent 和学生 Agent 两个角色，但它们本质上是几个独立的 `client.chat()` 包装函数。路由负责控制轮次，前端把完整对话历史作为请求参数，`write_code` 和 `fix_code` 也是彼此分开的调用。`ThinkingStageLog` 已经记录了部分交互，但没有统一的状态归约、工具协议和模型决策循环。

这次改造只覆盖阶段三。目标是让两个角色拥有完整的 Agent 运行时：模型根据用户目标和当前状态作出决策，按需调用有权限的工具，工具结果进入下一轮上下文，最终由运行时决定继续对话、进入代码审查还是完成会话。

## 2. 目标与非目标

### 目标

1. 为 Teacher Agent 和 Student Agent 提供统一的 Model、Tools、State、Memory 和 AgentLoop。
2. 让模型能够返回结构化决策，并通过工具完成状态读取、学习证据记录、错误代码生成和修复评估。
3. 让服务端以数据库事件为可信记忆来源，刷新页面或重新请求后可以恢复阶段三上下文。
4. 将标准答案、隐藏 Bug 和正确修复隔离在服务端及受控工具内，避免注入 Student Agent 的可见上下文。
5. 保留现有阶段三 API 和页面交互，逐步替换内部实现。
6. 为工具调用、决策循环、失败恢复和目标完成提供可测试的边界。

### 非目标

1. 本次不改造阶段一和阶段二。
2. 本次不引入新的外部 Agent 框架或新的模型供应商。
3. 本次不要求使用智谱或 OpenAI 的原生 Function Calling；先使用供应商无关的结构化决策协议。
4. 本次不改变课程题目、阶段一评分或阶段二答题规则。
5. 本次不实现跨学习会话的长期用户画像和多用户协作。

## 3. 现有约束与兼容策略

现有模型调用继续通过 `services/llm_client.py` 中的 `SharedLLMClient` 完成。新运行时只在它上面增加结构化决策解析，不直接依赖某一个供应商的响应对象。

现有路由继续保留：

- `/thinking/api/stage3/chat`
- `/thinking/api/stage3/teach`
- `/thinking/api/stage3/write_code`
- `/thinking/api/stage3/fix_code`

`routes/thinking.py` 改成鉴权、装配运行时和返回结果的适配层。`utils/thinking_ai.py` 继续承载阶段一、二逻辑，阶段三旧函数在迁移期间保留为兼容适配器。

前端现有的 `messages` 字段可以继续提交，但服务端不再把它当作可信历史。新代码以 `session_id`、当前用户消息和数据库事件恢复上下文，并继续返回 `ready_for_code` 等旧字段，减少页面改动。

优先复用 `ThinkingStageLog` 保存 Agent 事件，不给 `ThinkingSession` 增加必须立即迁移的状态列。已有的 `stage3_teacher_rounds` 和 `stage3_student_rounds` 继续维护为兼容统计字段，真正的 Agent 状态由事件和状态快照恢复。

## 4. 总体架构

```text
Stage 3 API
    |
    v
DualFeynmanRuntime
    |-- TeacherAgentSpec
    |-- StudentAgentSpec
    |-- AgentLoop
    |-- ToolRegistry
    |-- AgentState / FeynmanState
    `-- MemoryStore
            |
            `-- ThinkingStageLog

DualFeynmanRuntime --> StructuredDecisionModel --> SharedLLMClient
DualFeynmanRuntime --> Domain Services (code generation / fix evaluation)
```

计划新增 `utils/agents/` 包：

- `contracts.py`：`AgentState`、`FeynmanState`、`AgentDecision`、`ToolCall`、`ToolResult` 和 `AgentResult`。
- `model.py`：构造角色提示、请求结构化决策、解析 JSON、执行一次修复请求。
- `memory.py`：读取 `ThinkingStageLog`、生成角色记忆投影、归约状态、写入事件。
- `tools.py`：工具定义、参数 schema、角色权限、调用幂等和注册表。
- `loop.py`：执行模型决策、工具调用、状态更新和结束条件。
- `feynman.py`：装配两个角色的目标、提示规则和阶段三领域工具。

职责边界如下：

- Model 只负责提出决策，不直接修改数据库。
- Tool 负责领域动作和结构化状态变化，不负责决定下一步对话。
- MemoryStore 负责事件和状态恢复，不信任前端历史。
- AgentLoop 负责循环、权限校验、步数限制和最终结果。
- 路由只负责鉴权、读取课程对象、调用运行时和序列化响应。

运行时不代替 Agent 做教学判断。它可以阻止越权、无效状态和无限循环，但具体回复、是否查记忆、是否生成错误代码以及是否尝试完成目标，都由对应模型提出。

## 5. State 与 Memory

### 5.1 会话共享状态

`FeynmanState` 表示两个 Agent 共同面对的教学任务：

```json
{
  "session_id": 12,
  "goal": "teach_and_repair",
  "phase": "student_dialogue",
  "teacher_rounds": 2,
  "student_rounds": 4,
  "learning_evidence": [],
  "misconceptions": [],
  "buggy_code_event_id": null,
  "code_review_status": "pending",
  "status": "in_progress"
}
```

`goal` 由应用固定为阶段三目标，不允许模型自行改写。模型可以通过工具提交证据和完成请求，但最终状态由运行时校验。

### 5.2 Agent 私有状态

每个角色拥有自己的 `AgentState`：

```json
{
  "agent_id": "student_agent",
  "current_focus": "循环终止条件",
  "turn_index": 4,
  "last_user_message": "...",
  "last_decision": "ask_question",
  "goal_status": "in_progress"
}
```

Teacher Agent 的目标是帮助用户把理解讲清楚；Student Agent 的目标是模拟一个基础薄弱但可被教会的同学，暴露误区，并在证据充分后进入错误代码修复任务。

### 5.3 记忆分层与事件

Memory 分为三层：

1. 短期记忆：最近若干轮用户消息、Agent 回复和工具结果。
2. 教学记忆：已解释清楚的知识点、反复混淆的概念和未覆盖的关键步骤。
3. 内部工件：错误代码、隐藏 Bug 和修复评估结果。

事件写入 `ThinkingStageLog`，使用以下 `event_type`：

```text
agent_user_message
agent_decision
tool_call
tool_result
agent_message
state_snapshot
```

每个事件的 `metadata_json` 只保存必要的结构化元数据。模型提示词、API Key 和完整内部上下文不进入事件日志。

MemoryStore 为每个 Agent 生成不同的投影：

- Teacher Agent 可以读取用户当前解释、教学进度和错误类型。
- Student Agent 可以读取题目概念和用户刚才的讲解，但看不到标准答案、隐藏 Bug 和正确修复方案。
- `evaluate_fix` 工具可以读取隐藏工件，但只向 Agent 返回是否通过、反馈和下一步建议。

刷新或重新请求时，MemoryStore 从事件恢复最近消息和状态快照；前端传来的完整 `messages` 只用于旧接口兼容，不参与状态裁决。

## 6. Tool Registry 与角色权限

工具统一描述为：

```python
ToolDefinition(
    name="inspect_learning_state",
    description="读取当前教学进度和待解决的知识点",
    input_schema={...},
    allowed_roles={"teacher_agent", "student_agent"},
    handler=...
)
```

第一版工具保持小而明确：

| 工具 | Teacher Agent | Student Agent | 作用 |
|---|---:|---:|---|
| `inspect_learning_state` | 是 | 是 | 读取阶段、关键步骤和学习证据 |
| `recall_memory` | 是 | 是 | 查询历史解释、误区和未覆盖知识点 |
| `record_learning_evidence` | 是 | 是 | 保存结构化学习证据 |
| `generate_buggy_attempt` | 否 | 是 | 生成带初学者错误的代码工件 |
| `evaluate_fix` | 否 | 是 | 使用隐藏 Bug 评估用户提交的修复 |
| `complete_goal` | 是 | 是 | 请求结束当前目标，由运行时校验 |

工具返回统一结构：

```json
{
  "ok": true,
  "data": {},
  "public_message": "",
  "state_patch": {},
  "memory_events": []
}
```

工具调用必须满足以下约束：

- 工具名存在且当前角色有权限。
- 参数符合 schema，并限制文本长度。
- 有副作用的工具必须带 `call_id`，重复请求不能重复生成工件或记忆。
- 每个 Agent 请求有工具调用上限。
- 工具异常返回结构化错误，不把堆栈暴露给用户。
- 普通 Agent 文本继续经过 `sanitize_response`；错误代码作为独立代码审查工件返回。

## 7. Structured Decision 与 AgentLoop

模型返回供应商无关的决策结构：

```json
{
  "message": "你可以先解释一下循环为什么需要停止。",
  "tool_calls": [
    {
      "id": "call_01",
      "name": "record_learning_evidence",
      "arguments": {
        "concept": "循环终止条件",
        "evidence": "用户提到了循环结束条件"
      }
    }
  ],
  "goal_status": "in_progress",
  "ui_action": "continue_chat"
}
```

AgentLoop 的核心流程：

```text
1. 鉴权并校验 session_id 与当前用户的归属。
2. 读取数据库事件，恢复 FeynmanState 和当前 AgentState。
3. 写入当前用户消息，使用 request_id 防止重复写入。
4. 调用角色对应的 StructuredDecisionModel。
5. 校验决策；有工具调用则执行工具、记录事件、应用 state_patch。
6. 将工具结果加入下一轮上下文，最多重复 4 次模型决策。
7. 无工具调用时，清理并保存最终公共回复和 state_snapshot。
8. 返回公共消息、ui_action、兼容状态字段和有限的公开状态。
```

一次请求最多允许 4 次模型决策循环，避免无限调用工具和意外消耗额度。循环只能在以下情况结束：

- 模型生成普通回复；
- `complete_goal` 通过服务端校验；
- `generate_buggy_attempt` 生成代码审查工件；
- `evaluate_fix` 判定修复成功；
- 达到最大步数或遇到不可恢复错误。

`goal_status` 和 `ui_action` 不能直接改变数据库状态。模型声称完成时，运行时仍需要检查学习证据、阶段和工具结果；条件不足时拒绝完成并要求继续引导。

阶段三 API 返回保持兼容：

```json
{
  "success": true,
  "response": "小明的下一句回复",
  "agent": "student_agent",
  "ui_action": "show_code_review",
  "ready_for_code": true,
  "state": {
    "phase": "code_review",
    "goal_status": "in_progress"
  }
}
```

现有 `write_code` 和 `fix_code` 端点保留为兼容入口，内部调用 `generate_buggy_attempt` 和 `evaluate_fix` 对应的运行时路径。

## 8. 可靠性、安全与并发

### 8.1 模型和工具错误

模型输出无法解析时，先进行一次结构化修复请求；仍然失败则记录 `agent_decision_error`，返回安全引导语，不推进学习状态。

只读工具失败可以自动重试一次。有副作用的工具必须依靠 `call_id` 幂等，不能盲目重复执行。模型服务不可用时保留用户消息，但不增加 Agent 轮次，也不推进阶段。

### 8.2 输入和信息隔离

用户消息作为不可信输入，和系统提示、工具结果使用明确边界。工具权限、参数和状态变化由服务端校验，不由提示词保证。标准答案、隐藏 Bug 和正确修复不得进入 Student Agent 的可见上下文。

所有普通 Agent 回复继续经过物理代码过滤。内部工具数据不直接渲染到聊天气泡；错误代码只有在阶段三的代码审查面板中作为明确的教学工件展示。

### 8.3 会话并发

同一 `ThinkingSession` 同时只允许一个 Agent 请求修改事件记忆。运行时使用按 session 的互斥保护；部署了 Redis 时优先使用带过期时间的 Redis lock，没有 Redis 时使用进程内锁并依赖数据库写入事务。模型调用不持有数据库事务，只有事件追加和状态快照写入使用短事务。

每个请求携带或生成唯一 `request_id`，写入事件元数据。重复请求先检查已经完成的事件，直接返回已有结果，避免刷新或网络重试导致重复生成错误代码。

## 9. 测试策略

测试放在现有 `tests/` 下，至少覆盖：

1. 合同对象、决策解析器、schema 校验、工具注册表和 Memory reducer。
2. Fake Model 驱动的 AgentLoop：直接回复、连续工具调用、无效 JSON、未知工具、达到上限、拒绝完成、进入代码审查和修复成功。
3. Flask 路由：鉴权、会话归属、数据库恢复、忽略篡改后的前端历史、`ready_for_code` 兼容字段和重复 `request_id`。
4. 持久化回归：生成错误代码后能恢复隐藏 Bug，`fix_code` 能正确读取并评估。
5. 无 API Key 的端到端冒烟流程，以及现有项目测试回归。

不允许通过真实大模型调用作为单元测试前提。模型适配层使用 Fake Model 或可注入 transport，只有明确的手工冒烟测试才调用外部模型。

## 10. 迁移与验收标准

实施顺序：

1. 先新增 Agent contracts、MemoryStore、ToolRegistry 和 Fake Model 测试。
2. 实现 AgentLoop 和两个角色配置，不改变阶段三页面。
3. 将四个阶段三路由接入运行时，保留旧函数作为兼容适配器。
4. 修正错误代码工件和隐藏 Bug 的持久化，补齐 API 回归测试。
5. 最后调整 `thinking.js`，让新请求只提交当前消息，同时保留旧响应字段。

验收必须同时满足：

- Teacher Agent 和 Student Agent 都能恢复自己的历史和共享教学状态。
- 至少一次模型决策可以触发工具，工具结果会影响下一轮模型决策。
- 刷新页面不会丢失阶段三上下文，也不能通过篡改 `messages` 跳过轮次。
- 生成错误代码后能够进入代码审查面板，修复成功前会话不会完成。
- Student Agent 看不到标准答案、隐藏 Bug 和正确修复方案。
- 模型异常、工具异常和重复请求不会破坏事件记忆或错误推进阶段。
- 阶段一、阶段二和现有非 Agent 功能测试保持通过。

