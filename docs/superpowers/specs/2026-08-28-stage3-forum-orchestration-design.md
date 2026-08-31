# 第三阶段三角色论坛编排设计

**日期：** 2026-08-28  
**状态：** 待审阅  
**范围：** Stage 3 Feynman Teacher/Student runtime、论坛式展示、自动介入和代码审查触发

## 1. 背景与问题

当前 Stage 3 已经接入了 Teacher Agent、Student Agent、State、Memory、Tools 和有限步数 AgentLoop，但用户仍然在两个独立面板中交互。代码审查入口还保留了旧的前端触发方式，`feynman_rounds` 仍然容易把“聊够几轮”误当成“已经理解”。

下一版需要把三个人呈现为一条讨论流，同时保留严格的角色隔离：老师可以帮助用户理解概念，但老师的回答不能成为小明的知识，也不能让小明直接说“我也懂了”。小明应当围绕不同角度检查用户是否能够自行解释；当覆盖度达到条件时，自动生成一份带缺陷的代码供用户修复。

## 2. 目标与非目标

### 目标

1. 将用户、Teacher Agent、Student Agent 的公开发言按时间合并为一个论坛流，并保留明确的发言者、接收对象和回复关系。
2. 让“发给谁”由界面和服务端字段决定，不依赖用户在文字中输入“老师”或“小明”。
3. 保持 Teacher Agent 和 Student Agent 的角色记忆隔离。Teacher Agent 的回答可以展示给用户，但不能进入 Student Agent 的上下文，也不能被计入用户已掌握的证据。
4. 允许 Student Agent 根据脱敏的话题信号自动介入，但介入只能生成面向用户的追问，不能复述老师答案或宣称自己已经理解。
5. 用概念覆盖度和多角度探查替代固定轮数；每个概念最多有限次追问，理解后立即切换到其他概念。
6. 当服务端判定教学覆盖度达到门槛时，由 Student Agent 在 AgentLoop 中自动调用 `generate_buggy_attempt`，前端直接打开代码修复面板。
7. 保留旧接口和旧事件的兼容读取能力，避免已有 Stage 3 会话无法恢复。

### 非目标

1. 不把 Teacher Agent 和 Student Agent 变成脱离用户的无限自动对话。
2. 不向前端或学生展示隐藏 Bug、内部工具参数、私有状态或模型思考过程。
3. 不使用自然语言前缀解析“老师”或“小明”来决定路由。
4. 不在本次改动中重写 Stage 1、Stage 2 或通用 LLM provider。

## 3. 设计原则

### 3.1 屏幕可以合并，上下文不能合并

论坛是展示层投影。事件在数据库中保留明确的目标对象、可见范围和来源；每个 Agent 的 MemoryView 根据角色过滤事件。

Teacher Agent 的回答可以出现在用户看到的公共时间线中，但 Student Agent 的上下文只允许包含：

- 题目和关键概念；
- 用户明确发给 Student Agent 的解释；
- Student Agent 自己的历史消息和状态；
- 经过服务端脱敏的话题信号和探查任务。

Teacher Agent 的原始回答、教师内部判断和隐藏代码工件不进入 Student Agent 的上下文。

### 3.2 学习证据必须来自用户对小明的解释

用户向老师提问或阅读老师回答，只改变用户可见的讨论上下文，不直接产生 Student Agent 的 `learning_evidence`。只有带有 `target_role=student_agent` 的用户回答，才允许触发教学进度评估和证据记录。

### 3.3 模型可以提议，服务端决定是否推进

Agent 可以提议调用工具、发起介入或进入代码阶段，但服务端负责校验角色权限、参数、状态门槛、重复请求和代码审查结果。模型不能通过 `goal_status=complete` 或前端字段直接完成会话。

## 4. 交互模型

### 4.1 论坛输入框

论坛底部显示当前接收对象选择器：

```text
当前回复对象：[老师 Agent] [小明 Agent]
```

用户点击某条消息的“回复”操作时，选择器自动切换到对应对象，并保存 `reply_to_event_id`。用户不需要在文本中添加角色前缀。

如果没有明确选择对象，服务端返回 400，前端提示用户先选择接收对象；不进行静默猜测。未来可以支持“同时发送给双方”，但 Student Agent 仍然只能接收原始用户问题，不能接收 Teacher Agent 的回答。

### 4.2 请求协议

新的用户消息统一携带：

```json
{
  "session_id": 123,
  "message": "循环边界为什么这样写？",
  "target_role": "teacher_agent",
  "reply_to_event_id": "event-123",
  "request_id": "teacher-uuid"
}
```

`target_role` 只接受 `teacher_agent` 或 `student_agent`。`reply_to_event_id` 必须属于当前会话；它只负责论坛排序和因果追踪，不会改变角色权限。

后端兼容现有两个 Stage 3 端点：

- `/thinking/api/stage3/chat` 默认目标为 `teacher_agent`；
- `/thinking/api/stage3/teach` 默认目标为 `student_agent`。

新论坛端点可以统一调用编排器，旧端点继续作为兼容适配层。旧请求没有 `target_role` 时由端点上下文补全，而不是从文字内容猜测。

### 4.3 事件字段

继续使用 `ThinkingStageLog` 的 `metadata_json` 保存新增字段，不立即引入数据库迁移。新事件至少写入：

```json
{
  "request_id": "student-uuid",
  "target_role": "student_agent",
  "reply_to_event_id": "event-123",
  "message_kind": "user_message",
  "visibility": "public",
  "parent_request_id": "teacher-uuid",
  "source": "user"
}
```

自动介入和内部事件使用：

```json
{
  "message_kind": "student_probe",
  "target_role": "user",
  "visibility": "public",
  "parent_request_id": "teacher-uuid",
  "topic_signal": {
    "concept": "循环边界",
    "probe_dimension": "edge_case",
    "goal": "检查用户能否解释边界情况"
  }
}
```

隐藏 Bug 继续只写入 `tool_result` 或 `buggy_attempt` 的内部 `artifact`，公开响应仅包含 `buggy_code` 和安全提示。

## 5. Agent 编排与防干扰机制

### 5.1 角色上下文投影

新增统一的 `Stage3Orchestrator` 或等价的 runtime 编排层，负责：

1. 校验用户消息的目标对象和回复关系；
2. 写入公开用户消息事件；
3. 只向目标 Agent 的 AgentLoop 提供对应的 MemoryView；
4. 保存公开回复、工具事件和状态快照；
5. 根据安全的话题信号决定是否唤醒 Student Agent；
6. 限制一次用户请求最多产生一次自动介入，禁止介入递归。

论坛时间线可以显示 Teacher Agent 的回答，但 `MemoryStore.view_for(..., AgentRole.STUDENT_AGENT)` 必须明确排除 `teacher_agent` 的 `agent_message` 和教师工具结果。反过来，Teacher Agent 是否读取公开的小明问题由其角色投影决定，但 Teacher Agent 不会因为读取了论坛消息而自动改写 Student Agent 的状态。

### 5.2 脱敏话题信号

Teacher Agent 不得把自己的完整回答转发给 Student Agent。它最多通过 `request_student_probe` 提议一个结构化信号：概念、探查维度和探查目标。编排器清理其中的答案、标准代码、隐藏 Bug 和教师内部文本后，再创建 Student Agent 的 `intervention` 输入。

Student Agent 收到的是类似下面的任务：

```json
{
  "input_kind": "intervention",
  "concept": "循环边界",
  "probe_dimension": "edge_case",
  "goal": "检查用户能否用自己的话解释边界情况"
}
```

Student Agent 必须通过 `ask_student_probe` 或等价的受控动作生成问题。该动作的输出必须是面向用户的问题，不能是结论、标准答案或“我也懂了”。服务端拒绝缺少问题目标、重复维度或明显答案泄露的介入结果。

### 5.3 自动介入边界

- Teacher Agent 可以产生一次 Student Agent 探查信号。
- Student Agent 不自动唤醒 Teacher Agent。
- 每个用户请求最多一次自动介入。
- 自动介入不能再次产生自动介入。
- 介入失败只记录结构化错误，不推进学习状态。
- 用户后续点击“回答小明”时，才会产生计入 Student Agent 学习评估的用户消息。

## 6. 基于覆盖度的教学状态机

### 6.1 新增状态

在 `FeynmanState` 或其持久化的 `state_snapshot` 中增加概念覆盖信息：

```json
{
  "concept_coverage": {
    "循环边界": {
      "status": "covered",
      "asked_dimensions": ["core", "edge_case"],
      "accepted_evidence_count": 1,
      "attempts": 2,
      "last_evidence_event_id": "event-456"
    }
  },
  "coverage_score": 0.8,
  "unresolved_concepts": [],
  "ready_for_code": false
}
```

预设通过 `difficulty_config.feynman_coverage` 提供可调整策略；默认值为：

```json
{
  "min_coverage": 0.8,
  "max_probes_per_concept": 2,
  "probe_dimensions": ["core", "edge_case", "application"]
}
```

如果旧预设没有该配置，则由 `key_steps` 推导概念集合，并使用默认策略。`feynman_rounds` 只作为旧会话读取兼容字段，不再作为新会话进入代码阶段的依据。

### 6.2 探查策略

1. Student Agent 先从未覆盖概念中选择一个未使用的探查维度。
2. 用户回答后，Student Agent 使用 `assess_teaching_progress` 或等价工具评估回答是否包含具体概念、因果关系或应用说明。
3. 回答达到条件时立即标记该概念为 `covered`，不再继续追问同一概念。
4. 回答不足时最多换一个维度追问一次；不能原句改写后重复提问。
5. 达到单概念最大次数后，记录 `partial` 并切换到下一个概念；是否允许带有未解决概念进入代码阶段由 `min_coverage` 和预设策略决定。
6. 只有用户发给 Student Agent 的解释可以产生 `learning_evidence`；Teacher Agent 的消息不会改变覆盖度。

### 6.3 自动代码审查

当覆盖度达到服务端门槛后：

1. Student Agent 的下一次结构化决策必须优先调用 `generate_buggy_attempt`。
2. `generate_buggy_attempt` 工具再次检查 `teaching_gate`，模型不能提前生成代码绕过覆盖度。
3. 工具成功后返回 `ui_action=show_code_review` 和公开的 `buggy_code`。
4. 新前端直接打开代码修复面板，不需要用户输入“你先写一段代码”。
5. `/thinking/api/stage3/write_code` 保留为旧前端和开发调试入口，但同样必须通过服务端门槛。
6. 用户提交错误修复时保持 `code_review_status=failed`，不能完成会话；只有服务端验证通过后才允许写入 `stage_pass` 和完成状态。

## 7. 前端展示

### 7.1 论坛时间线

Stage 3 使用单条时间线显示：

- 用户消息；
- Teacher Agent 回复；
- Student Agent 追问；
- 代码审查卡片；
- 代码修复反馈。

每条消息显示角色头像、角色名、时间和必要的“回复某人”关系。`agent_decision`、`tool_call`、隐藏 Bug 和完整状态快照不进入学生公共流。

开发者调试面板增加可选的 Agent Trace 视图，显示 `target_role`、`input_kind`、`tool_call.name`、`coverage_score` 和 `ui_action`，但仍隐藏标准答案和 Bug 细节。

### 7.2 旧页面兼容

旧的 Teacher/Student 双栏 DOM 可以先由论坛时间线替代；旧恢复字段 `teacher_history`、`student_history` 继续由服务端生成，确保旧前端或历史会话不会丢失。新前端只依赖公开事件投影，不把本地数组作为服务端状态来源。

## 8. 错误处理与安全边界

- 无效 `target_role`、越权 `reply_to_event_id` 或缺少目标对象：400。
- 会话不属于当前用户：403。
- Stage 3 未激活：409。
- 预设或 runtime 不可用：503。
- Student Agent 试图读取教师私有消息：上下文构建阶段过滤，不能依赖提示词自觉。
- Student Agent 试图提前生成代码：工具返回 `CODE_REVIEW_NOT_READY`，不推进状态。
- Student Agent 试图用介入消息声明已理解：动作校验失败，不写入学习证据。
- 重复 `request_id`：返回第一次公开结果，不新增终结事件或重复执行副作用工具。
- AgentLoop 超过最大模型步数：返回结构化错误，不修改完成状态。

## 9. 迁移与兼容策略

1. 新事件写入显式的 `target_role`、`message_kind` 和 `reply_to_event_id`。
2. 旧 `chat`、`write_code`、`fix_code` 事件按原有 `panel` 和 `role` 字段恢复。
3. 旧 runtime 事件没有目标字段时，在读取阶段根据事件类型推导，不回写历史数据。
4. `feynman_rounds` 只用于旧会话恢复和兼容提示；新会话使用 `feynman_coverage`。
5. 旧 `/stage3/write_code` 请求仍可工作，但不能绕过新的服务端 coverage gate。

## 10. 测试计划

### 编排与隔离

- 论坛按事件时间和 `reply_to_event_id` 稳定排序。
- Teacher Agent 的回答不出现在 Student Agent 的 context、visible messages 或 learning evidence 中。
- 用户向老师提问不会被计作已教会小明。
- Student Agent 自动介入只收到话题信号，不收到教师原文、标准答案或隐藏 Bug。
- 一次用户请求最多一次介入，介入不能递归唤醒 Agent。
- 非问题式介入、重复维度和答案泄露被拒绝。

### 覆盖度与自动代码

- 一个概念第一次解释清楚后立即切换，不追加无意义追问。
- 解释不充分时允许一次不同维度追问，超过上限后切换概念。
- `feynman_rounds` 变化不会单独触发代码阶段。
- 覆盖度达到门槛后 Student Agent 自动调用 `generate_buggy_attempt`。
- 覆盖度未达到门槛时直接调用写代码工具会失败。
- 错误修复不完成会话，正确修复才推进 `stage_pass`。

### 接口与回归

- 新论坛请求的目标字段校验、缺失目标和跨会话回复校验。
- 旧 Stage 3 端点的请求兼容性。
- 刷新页面后论坛投影、覆盖度和代码审查面板可恢复。
- 相同 `request_id` 重试保持幂等。
- 现有 Stage 3 Agent 合同、Memory、Tools、AgentLoop、Routes 测试全部通过。
- 前端语法检查和完整项目回归测试通过；若存在与本次改动无关的冻结研究配置失败，必须单独记录，不修改研究基线。

## 11. 验收标准

完成后，使用者可以在一个 Stage 3 论坛中按以下顺序体验：

```text
用户选择“问老师”并提问
老师回答，但回答不进入小明记忆
系统只生成“循环边界/边界情况”话题信号
小明自动发起一个新的边界问题
用户选择“回答小明”并用自己的话解释
小明换一个概念或维度，不重复纠缠
覆盖度达到门槛后小明自动生成错误代码
用户修复代码，服务端验证后完成 Stage 3
```

验收时至少需要在 Agent Trace 中确认：

1. Teacher Agent 和 Student Agent 使用不同的角色上下文；
2. Teacher Agent 的回答没有进入 Student Agent 的消息列表；
3. `target_role` 由界面选择产生，而不是由文本前缀产生；
4. 自动代码生成由 coverage gate 和 Student Agent 工具调用触发，而不是由固定轮数或用户口令触发。
