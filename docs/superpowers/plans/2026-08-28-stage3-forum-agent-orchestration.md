# Stage 3 Forum Agent Orchestration Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 将 Stage 3 改造成一条三角色论坛流，同时保持 Teacher Agent 与 Student Agent 的上下文隔离，让小明按概念覆盖度自动介入，并在达到门槛后自动生成待修复代码。

**Architecture:** 论坛时间线只负责展示公开事件；消息的 target_role、reply_to_event_id 和 parent_request_id 由服务端保存并用于路由。Teacher Agent 的完整回复不会进入 Student Agent 的 MemoryView，Teacher Agent 只能产生脱敏的话题信号，Student Agent 再决定是否用受控工具向用户发起追问。新的 coverage gate 由服务端计算，取代固定 feynman_rounds；通过后 Student Agent 在同一个 AgentLoop 中调用 generate_buggy_attempt。

**Tech Stack:** Python 3.8+、Flask、SQLAlchemy、pytest、Jinja2、Bootstrap 5、原生 JavaScript、现有 AgentLoop、MemoryStore、ToolRegistry。

**Spec:** docs/superpowers/specs/2026-08-28-stage3-forum-orchestration-design.md

## Global Constraints

- 用户消息的目标对象由界面发送的 target_role 决定，不从文字前缀解析“老师”或“小明”。
- Teacher Agent 的 agent_message、内部工具结果、标准答案和隐藏 Bug 不得进入 Student Agent 的上下文。
- 只有目标为 student_agent 的用户解释可以增加新的 coverage evidence；Teacher Agent 的回答不能单独完成覆盖度。
- 每个概念默认最多探查 2 次；第二次必须使用不同的探查维度。
- 每个用户请求最多触发 1 次 Student Agent 自动介入，自动介入不能递归唤醒其他 Agent。
- generate_buggy_attempt 必须通过服务端 coverage gate；不能靠前端字段或固定轮数绕过。
- 保留旧 Stage 3 端点、旧事件读取和旧恢复字段的兼容能力。
- 只在 E:/CodeSense/stage3-forum-agent-interaction 修改业务代码，避免污染论文工作区。
- 每个任务先补充失败测试，再实现最小变更，最后运行该任务的回归测试并提交一个小 commit。

## Task 1: Add forum message and state contracts

**Files**

- Add tests/test_stage3_forum_contracts.py.
- Modify utils/agents/contracts.py.

**Tests first**

- 验证 Stage3Target 至少包含 teacher_agent、student_agent、user、system。
- 验证 Stage3MessageKind 至少包含 user_message、agent_message、student_probe、agent_trigger。
- 构造 ForumEnvelope，断言 to_metadata() 输出 target_role、message_kind、reply_to_event_id、parent_request_id、visibility 和 request_id。
- 验证 FeynmanState 的新默认字段：concept_coverage、coverage_score、unresolved_concepts、ready_for_code、pending_probe。
- 验证 AgentResult.to_public_dict() 不泄露 internal_signals。

**Implementation**

- 增加可序列化的 Stage3Target 和 Stage3MessageKind 枚举。
- 增加 ForumEnvelope 数据类，字段为 request_id、source、target、content、message_kind、reply_to_event_id、parent_request_id、visibility；提供 to_metadata()。
- 扩展 FeynmanState，并保持旧的 feynman_rounds、key_concepts、learning_evidence 等字段可读取。
- 给 AgentResult 增加 internal_signals，仅供编排器使用，不进入公共 JSON。
- 保持旧状态 JSON 的缺失字段兼容，恢复时使用安全默认值。

**Verification and commit**

- 运行 python -m pytest tests/test_stage3_forum_contracts.py tests/test_stage3_agent_memory.py -q。
- 运行 git diff --check。
- 提交 feat: add stage3 forum message contracts。

## Task 2: Project role-aware forum memory

**Files**

- Add tests/test_stage3_forum_memory.py.
- Modify utils/agents/memory.py.

**Tests first**

- 写入同一 session 的 teacher-target 用户问题、teacher agent 回复、student-target 用户解释、student probe。
- 断言 forum_events(session_id) 只返回可公开展示的 user_message、agent_message、student_probe，不返回工具调用、工具结果或隐藏 artifact。
- 断言 student view 包含目标为 student_agent 的用户解释和 Student Agent 的消息，但不包含 Teacher Agent 回复。
- 断言旧 chat 事件可以根据 metadata.panel 推断兼容目标。
- 断言 teacher agent 的答案不能成为 Student Agent 的 evidence。

**Implementation**

- 为 EventRecord/MemoryStore 增加 target_role、message_kind、visibility 等元数据的读取和写入约定。
- 增加 MemoryStore.forum_events(session_id)，按时间排序返回脱敏的公开事件。
- 为 view_for(session_id, role=student_agent) 增加严格的 MemoryView 投影：只允许 Student Agent 自己的公开消息、student-target 用户消息及其受控 signal。
- Teacher Agent 的 agent_message、teacher tool_call/tool_result、参考答案和隐藏代码一律排除在 Student Agent context 之外。
- 对旧记录保留 metadata.panel、role 和 event_type 的推断逻辑，避免破坏历史会话恢复。

**Verification and commit**

- 运行 python -m pytest tests/test_stage3_forum_memory.py tests/test_stage3_agent_memory.py tests/test_stage3_agent_loop.py -q。
- 提交 feat: project stage3 memory by forum target。

## Task 3: Implement concept coverage reducer and gate

**Files**

- Add utils/agents/coverage.py.
- Add tests/test_stage3_coverage.py.

**Public interfaces**

    @dataclass(frozen=True)
    class CoverageConfig:
        min_coverage: float = 0.8
        max_probes_per_concept: int = 2
        probe_dimensions: Tuple[str, ...] = ("core", "edge_case", "application")

    @dataclass(frozen=True)
    class CoverageDecision:
        concept_status: str
        attempts: int
        next_concept: Optional[str]
        next_dimension: Optional[str]
        ready_for_code: bool
        coverage_score: float
        state_patch: Dict[str, Any]

    def load_coverage_config(raw, key_concepts) -> CoverageConfig
    def apply_coverage_assessment(state, key_concepts, *, config, concept,
                                  dimension, assessment, evidence, event_id)
        -> CoverageDecision

**Tests first**

- 验证旧配置没有 coverage 字段时得到安全默认值。
- 第一次对概念 core 评为 covered 后，概念进入完成状态，下一次探查不重复该概念。
- 两次 partial 必须使用不同 dimension；第三次或重复 dimension 抛出 ValueError。
- off_topic 和无效/空 evidence 消耗尝试次数，但不能伪造 covered。
- 未达到 min_coverage 时 ready_for_code 为 false；所有概念覆盖且 score 达标时为 true。
- 覆盖度计算使用概念权重一致的确定性规则，边界值可测试。

**Implementation**

- 用纯函数实现状态 reducer，不直接修改 AgentLoop 的快照对象。
- 对 concept、dimension、assessment、evidence、event_id 做严格校验。
- covered 立即完成当前概念；partial/off_topic 在达到上限后结束当前概念。
- 每个概念最多 max_probes_per_concept 次；选择下一个探查时跳过已用维度。
- 将 state_patch 设计为可直接合并到 FeynmanState 的最小字段集合。
- gate 同时检查 coverage_score >= min_coverage 且 pending_probe 为空。

**Verification and commit**

- 运行 python -m pytest tests/test_stage3_coverage.py -q。
- 提交 feat: add stage3 concept coverage gate。

## Task 4: Add bounded probe tools and trigger support

**Files**

- Modify utils/agents/tools.py.
- Modify utils/agents/loop.py.
- Extend tests/test_stage3_agent_tools.py.
- Extend tests/test_stage3_agent_loop.py.

**Tests first**

- Teacher Agent 可以调用 request_student_probe，但只能产生 concept、dimension、goal 组成的内部脱敏 signal。
- Student Agent 可以调用 ask_student_probe；question 为空、不是问句或包含“我也懂了”“我知道答案”等自我确认文本时必须拒绝。
- assess_teaching_progress 只能由 Student Agent 调用，并将 coverage reducer 的 state_patch 写回状态。
- 非目标角色调用受限工具时返回稳定错误，不产生公开事件。
- handle_trigger 写入 agent_trigger，不写入空的 agent_user_message。
- 一个请求至多执行一次 intervention，intervention 不能再次触发 Agent。

**Implementation**

- 扩展 ToolResult，增加不公开的 internal_content 和 signal_type。
- 扩展 ToolContext，加入 input_kind、target_role、coverage_config、trigger。
- 增加 teacher-only request_student_probe。
- 增加 student-only ask_student_probe 和 assess_teaching_progress。
- 保留旧 record_learning_evidence 的兼容行为，但新的自动代码门禁只读 coverage state。
- 在 AgentLoop 增加 handle_trigger(trigger, request_id)，使用 input_kind=intervention，并沿用 max_model_steps 的上限。
- AgentResult 收集 internal_signals，公共序列化继续过滤内部字段。

**Verification and commit**

- 运行 python -m pytest tests/test_stage3_agent_tools.py tests/test_stage3_agent_loop.py tests/test_stage3_agent_contracts.py -q。
- 提交 feat: add bounded stage3 probe interventions。

## Task 5: Orchestrate the three-role forum turn

**Files**

- Add utils/agents/orchestrator.py.
- Modify utils/agents/feynman.py.
- Modify utils/agents/__init__.py.
- Add tests/test_stage3_forum_orchestrator.py.

**Public interfaces**

    @dataclass
    class ForumTurnResult:
        primary: AgentResult
        interventions: List[AgentResult] = field(default_factory=list)

        def to_public_dict(self) -> Dict[str, Any]:
            ...

    class Stage3Orchestrator:
        def __init__(self, runtime):
            ...

        def handle_user_message(self, message, *, target_role, request_id,
                                reply_to_event_id=None) -> ForumTurnResult:
            ...

**Tests first**

- target_role=teacher_agent 时，Teacher Agent 正常回答；Student Agent 的模型 context 不包含该回答。
- Teacher Agent 最多产生一个 sanitized topic signal；signal 不包含完整回答、参考答案或 hidden code。
- target_role=student_agent 时，用户解释进入 Student Agent context，并能触发受控追问。
- 学生介入内容必须是问题，不得出现“我也懂了”式旁观发言。
- 同一个用户请求最多返回一个 intervention，不能递归触发。
- coverage gate 未通过时 generate_buggy_attempt 不得执行；通过后 AgentLoop 自动调用该工具。
- Student Agent 普通文字未调用工具时，下一步返回结构化 READY_FOR_CODE_REQUIRED，而不是依赖固定轮数。

**Implementation**

- 将 DualFeynmanRuntime 的 handle_chat 扩展为接收 event_metadata，并增加 handle_trigger。
- 编排器保存 ForumEnvelope 的 parent_request_id/reply_to_event_id，并把同一请求的公开事件聚合为一条结果。
- Teacher Agent 的模型输出只用于 Teacher public reply；给 Student Agent 的输入只有脱敏 signal。
- Student Agent 只接收 student-target 用户内容、自己的历史和 signal，不接收 Teacher Agent 内容。
- 当 assess_teaching_progress 返回 ready_for_code 时，在同一条受限 AgentLoop 中推动 generate_buggy_attempt。
- generate_buggy_attempt 仍由服务端 gate 校验，未就绪返回稳定的 CODE_REVIEW_NOT_READY。

**Verification and commit**

- 运行 python -m pytest tests/test_stage3_forum_orchestrator.py tests/test_stage3_agent_loop.py tests/test_stage3_agent_memory.py -q。
- 提交 feat: orchestrate stage3 forum agent turns。

## Task 6: Expose the target-aware Stage 3 API

**Files**

- Modify routes/thinking.py.
- Add tests/test_stage3_forum_routes.py.
- Extend existing Stage 3 route tests.

**Tests first**

- POST /thinking/api/stage3/forum/message 缺少 target_role 时返回 400 和 TARGET_ROLE_REQUIRED。
- target_role 非法时返回 400；reply_to_event_id 不属于当前 session 时返回 REPLY_EVENT_NOT_FOUND。
- 正确请求将 session_id、target_role、reply_to_event_id 和 request_id 传给编排器。
- JSON 返回 primary 和 interventions，且不包含 internal_signals、tool arguments 或完整 state decision。
- 旧 /stage3/chat 默认 teacher_agent，旧 /stage3/teach 默认 student_agent。
- start_session 返回 forum_history，旧 teacher_history/student_history 字段仍可恢复。
- write_code 端点保留，但 coverage gate 未通过时不能绕过。

**Implementation**

- 增加严格的 forum message 路由和请求字段校验。
- 使用 session ownership 检查 reply_to_event_id，禁止跨会话引用。
- 保留 _extract_stage3_message 作为旧客户端 fallback，但不从消息正文解析目标角色。
- 使用 MemoryStore.forum_events 生成 sanitized forum_history。
- 统一错误响应结构，确保前端可以区分目标字段错误、引用错误和未达到代码门禁。

**Verification and commit**

- 运行 python -m pytest tests/test_stage3_forum_routes.py tests/test_stage3_agent_routes.py -q。
- 提交 feat: expose stage3 forum routing API。

## Task 7: Replace split Stage 3 panels with a target-aware forum UI

**Files**

- Modify templates/thinking/arena.html.
- Modify static/js/thinking.js.
- Modify static/css/thinking.css.
- Extend tests/test_dev_debug_panel.py or add tests/test_stage3_forum_ui.py.

**Tests first**

- 模板包含 stage3-forum、forum-feed、forum-target-teacher、forum-target-student、forum-input、forum-send 和 forum-reply-context。
- 默认 target_role 为 teacher_agent，两个 target controls 有可见选中状态和 ARIA 属性。
- sendForumMessage 的 JSON 包含 session_id、message、target_role、reply_to_event_id、request_id，不上传完整 history 数组。
- 渲染 primary 和 interventions 时显示来源角色、回复关系和可用的 reply action。
- 收到 student_probe 时自动将目标切换到 student_agent；收到 buggy_code/ui_action 时打开代码修复区。

**Implementation**

- 将 Stage 3 公开交互合并成单一 forum feed；保留教师/小明角色按钮用于选择收件人。
- 增加 reply context、request id 和 pending 状态，避免重复提交。
- 通过 /stage3/forum/message 发送消息，旧接口仅作为兼容 fallback。
- 渲染公开事件时不展示 tool_call、tool_result、internal signal 或隐藏代码。
- 保留现有代码审查编辑器和提交修复逻辑。
- 在浏览器端只保存 UI 所需的公开 forum_history，不复制 Agent Memory。

**Verification and commit**

- 运行 node --check static/js/thinking.js。
- 运行 python -m pytest tests/test_dev_debug_panel.py tests/test_stage3_forum_ui.py -q。
- 提交 feat: render stage3 as a target-aware forum。

## Task 8: Restore state, add safe trace, and run regression

**Files**

- Modify routes/thinking.py, static/js/thinking.js, static/css/thinking.css as needed for restore and trace.
- Add or extend tests/test_stage3_forum_restore.py and tests/test_stage3_forum_trace.py.

**Tests first**

- 恢复后的 forum_history 只含公开消息，Teacher Agent 的完整答案和工具结果不可见。
- 刷新后 target、reply context 和当前 coverage summary 可以恢复。
- 本地调试面板可折叠，并从 session log 映射安全字段：event_type、role、target_role、input_kind、tool_name、coverage_score、ui_action。
- trace 不包含 artifacts、reference code、full decisions、内部 signal 或完整 prompt。
- 没有 session 时 trace 和 forum 恢复都返回稳定的空状态/错误。

**Implementation**

- 将 Agent Trace 作为 local-only 的开发辅助展示，不改变公开论坛协议。
- 保持调试面板折叠默认值，确保不遮挡完整页面。
- 补齐旧字段恢复和新字段默认值，处理旧会话没有 coverage 的情况。
- 清理前端调试输出中的完整响应、模型上下文和工具参数。

**Verification**

- 运行 python -m pytest tests/test_stage3_forum_contracts.py tests/test_stage3_forum_memory.py tests/test_stage3_coverage.py tests/test_stage3_forum_orchestrator.py tests/test_stage3_forum_routes.py tests/test_stage3_forum_restore.py tests/test_stage3_forum_trace.py tests/test_stage3_agent_contracts.py tests/test_stage3_agent_memory.py tests/test_stage3_agent_tools.py tests/test_stage3_agent_loop.py tests/test_stage3_agent_routes.py tests/test_dev_debug_panel.py -q --disable-warnings。
- 运行 node --check static/js/thinking.js。
- 运行 git diff --check。
- 在干净的临时测试环境中运行 python -m pytest tests -q；若只出现既有的 simulation freeze/研究数据不一致失败，记录证据，不修改论文或研究文件来掩盖它。
- 最后检查 git status --short --branch、git diff --stat 和关键文件 diff，确认没有意外改动。
- 完成用户手测前不合并、不删除实现分支；保留可复现的分支启动命令。
- 用户确认手测通过后，再按 finishing-a-development-branch 流程创建/更新 PR、合并 main，并删除临时工作树。

## Execution Notes

- 实现阶段使用 superpowers:subagent-driven-development；每个任务先由测试锁定行为，再由实现代理完成，主代理负责审阅和验证。
- 任何与论文、simulation、research_exports 相关的既有修改均不属于本功能范围。
- 若发现现有 API 与计划接口冲突，优先增加兼容适配层，不直接删除旧字段或旧端点。
- 测试失败时先使用 systematic-debugging 定位根因；不要通过放宽断言或绕过 coverage gate 让测试虚假通过。
