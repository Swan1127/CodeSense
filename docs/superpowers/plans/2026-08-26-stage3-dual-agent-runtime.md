# Stage 3 Dual-Agent AgentLoop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把阶段三的 Teacher Agent 和 Student Agent 从无状态聊天函数升级为共享 State/Memory、可调用工具、模型决策驱动的双智能体 AgentLoop。

**Architecture:** 在 `utils/agents/` 中建立供应商无关的运行时。`StructuredDecisionModel` 通过现有 `SharedLLMClient` 读取 JSON 决策，`ToolRegistry` 校验并执行角色工具，`MemoryStore` 从 `ThinkingStageLog` 恢复事件和状态，`AgentLoop` 串起多轮模型决策。阶段三路由保留原 URL，前端逐步改成只提交当前消息。

**Tech Stack:** Python 3.8+、Flask、Flask-SQLAlchemy、SQLAlchemy、现有 `SharedLLMClient`、pytest、现有 Bootstrap/Jinja/原生 JavaScript。

**Spec:** `docs/superpowers/specs/2026-08-24-stage3-dual-agent-runtime-design.md`

## Global Constraints

- 本次只改造阶段三；阶段一、阶段二和其他业务模块保持原有行为。
- 不增加新的 LLM 供应商，也不依赖供应商原生 Function Calling；模型通过 JSON 决策协议选择工具。
- `ThinkingStageLog` 是阶段三 Agent 事件的持久化来源；前端 `messages` 只能兼容读取，不能作为可信状态。
- Student Agent 的上下文不能包含标准答案、隐藏 Bug 或正确修复方案。
- 一次请求最多执行 4 次模型决策，工具参数和角色权限必须由服务端校验。
- 有副作用的工具必须使用 `request_id`/`call_id` 幂等；错误不能推进学习阶段。
- 普通 Agent 回复继续经过 `sanitize_response`；内部工件只能通过明确的代码审查字段返回，不能进入普通聊天文本。
- 同一 `ThinkingSession` 同时只允许一个 Agent 请求写入事件；模型调用不持有数据库事务，事件追加和状态快照使用短事务。
- 模型不可用或决策解析失败时保留用户消息，不增加 Agent 轮次、不推进阶段，并记录 `agent_decision_error`。
- 单元测试不调用真实大模型，统一使用 Fake Model、Fake Tool 或可注入 callback。
- 所有提交只包含当前任务的文件；不要暂存工作区已有的研究、输出和临时文件改动。
- 基线测试使用 `& 'E:\anaconda\python.exe' -m pytest tests -q`，不要从仓库根目录直接运行 pytest，因为根目录的二进制 `test_results.txt` 会被误收集。

---

## 文件边界

先锁定每个文件的职责，后续任务不要把领域逻辑重新塞回路由：

- Create `utils/agents/__init__.py`：导出公开运行时类型和工厂。
- Create `utils/agents/contracts.py`：Agent 角色、状态、决策、工具调用、工具结果和 API 结果的数据合同。
- Create `utils/agents/memory.py`：SQLAlchemy 事件存储、状态归约、短期记忆和角色投影。
- Create `utils/agents/model.py`：结构化 JSON 决策解析、一次修复请求和模型 fallback。
- Create `utils/agents/tools.py`：工具定义、权限、schema 校验、幂等和阶段三工具 handler。
- Create `utils/agents/loop.py`：有限步数的模型决策循环。
- Create `utils/agents/feynman.py`：Teacher/Student 角色配置、运行时装配和代码工件适配。
- Modify `routes/thinking.py:15-21,174-211,688-921,1110-1122`：接入运行时，恢复新事件类型，保留旧 API 字段。
- Modify `static/js/thinking.js:1047-1219`：发送当前消息和 request id，消费新的 UI action。
- Create `tests/test_stage3_agent_contracts.py`：纯数据合同与决策解析测试。
- Create `tests/test_stage3_agent_memory.py`：事件归约、角色记忆隔离和幂等测试。
- Create `tests/test_stage3_agent_loop.py`：Fake Model 驱动的工具循环测试。
- Create `tests/test_stage3_agent_tools.py`：工具权限、参数、隐藏数据和领域 callback 测试。
- Create `tests/test_stage3_agent_routes.py`：阶段三 Flask 路由、持久化和兼容响应测试。

不修改 `models.py` 的表结构；新增事件类型都短于现有 `event_type` 的 50 字符限制，状态继续通过 `metadata_json` 的 `state_snapshot` 事件保存。

## Task 1: 建立 Agent 数据合同

**Files:**
- Create: `utils/agents/__init__.py`
- Create: `utils/agents/contracts.py`
- Test: `tests/test_stage3_agent_contracts.py`

**Interfaces:**
- Consumes: 无；该任务只依赖 Python 标准库 `dataclasses`、`enum`、`typing` 和 `json`。
- Produces: `AgentRole`、`GoalStatus`、`UIAction`、`ToolCall`、`AgentDecision`、`ToolResult`、`FeynmanState`、`AgentState`、`AgentResult`。

- [ ] **Step 1: 写决策和状态的失败测试**

```python
def test_agent_decision_parses_tool_call_and_defaults_message():
    decision = AgentDecision.from_payload({
        "tool_calls": [{
            "id": "call-1",
            "name": "inspect_learning_state",
            "arguments": {}
        }]
    })

    assert decision.message == ""
    assert decision.tool_calls[0].call_id == "call-1"
    assert decision.goal_status == GoalStatus.IN_PROGRESS
    assert decision.ui_action == UIAction.CONTINUE_CHAT


def test_agent_decision_rejects_malformed_tool_call():
    with pytest.raises(ValueError, match="tool call"):
        AgentDecision.from_payload({
            "tool_calls": [{"name": "inspect_learning_state"}]
        })
```

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py -q`

Expected: FAIL，因为 `utils.agents` 和数据合同尚未存在。

- [ ] **Step 3: 实现最小数据合同**

实现以下稳定字段，并在 `from_payload` 中拒绝缺少 `id/name/arguments` 的工具调用：

```python
@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: Dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ToolCall":
        if not isinstance(payload, Mapping):
            raise ValueError("tool call must be an object")
        if not payload.get("id") or not payload.get("name") or "arguments" not in payload:
            raise ValueError("tool call requires id, name and arguments")
        arguments = payload["arguments"]
        if not isinstance(arguments, dict):
            raise ValueError("tool call arguments must be an object")
        return cls(
            call_id=str(payload["id"]),
            name=str(payload["name"]),
            arguments=dict(arguments),
        )


@dataclass
class AgentDecision:
    message: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    goal_status: GoalStatus = GoalStatus.IN_PROGRESS
    ui_action: UIAction = UIAction.CONTINUE_CHAT

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AgentDecision":
        if not isinstance(payload, Mapping):
            raise ValueError("decision payload must be an object")
        raw_tool_calls = payload.get("tool_calls", [])
        if not isinstance(raw_tool_calls, list):
            raise ValueError("tool_calls must be a list")
        tool_calls = [ToolCall.from_payload(item) for item in raw_tool_calls]
        return cls(
            message=str(payload.get("message", "")),
            tool_calls=tool_calls,
            goal_status=GoalStatus(payload.get("goal_status", GoalStatus.IN_PROGRESS)),
            ui_action=UIAction(payload.get("ui_action", UIAction.CONTINUE_CHAT)),
        )
```

`AgentDecision` 同时实现 `to_payload()`，把枚举序列化为字符串，供 `agent_decision` 事件记录和后续模型上下文使用。`FeynmanState` 至少包含固定的 `session_id/goal/phase/teacher_rounds/student_rounds/learning_evidence/misconceptions/buggy_code_event_id/code_review_status/status`；`AgentState` 至少包含 `agent_id/current_focus/turn_index/last_user_message/last_decision/goal_status`。这些字段都从 `ThinkingStageLog` 事件归约，模型只能提交经工具校验的 patch。

`ToolResult` 必须区分 `model_content` 和 `public_content`，让错误代码可以返回给代码审查面板，但不会自动进入 Student Agent 的普通提示词：

```python
@dataclass
class ToolResult:
    ok: bool
    model_content: Dict[str, Any] = field(default_factory=dict)
    public_content: Dict[str, Any] = field(default_factory=dict)
    state_patch: Dict[str, Any] = field(default_factory=dict)
    memory_events: List[Dict[str, Any]] = field(default_factory=list)
    error_code: Optional[str] = None
    retryable: bool = False
```

对外结果合同必须只暴露公开字段：

```python
@dataclass
class AgentResult:
    success: bool
    agent: AgentRole
    response: str = ""
    ui_action: UIAction = UIAction.CONTINUE_CHAT
    ready_for_code: bool = False
    state: Dict[str, Any] = field(default_factory=dict)
    public_content: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "response": self.response,
            "agent": self.agent.value,
            "ui_action": self.ui_action.value,
            "ready_for_code": self.ready_for_code,
            "state": self.state,
            **self.public_content,
        }
        if self.error_code:
            result["error_code"] = self.error_code
        return result
```

- [ ] **Step 4: 运行测试并补齐边界**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py -q`

Expected: PASS；同时覆盖枚举非法值、非对象 payload、过长消息字段和 `AgentResult.to_public_dict()` 不泄露内部字段。

- [ ] **Step 5: 提交合同层**

```powershell
git add -- utils/agents/__init__.py utils/agents/contracts.py tests/test_stage3_agent_contracts.py
git commit -m "feat: add stage3 agent contracts"
```

## Task 2: 实现事件 MemoryStore 和状态归约

**Files:**
- Create: `utils/agents/memory.py`
- Test: `tests/test_stage3_agent_memory.py`

**Interfaces:**
- Consumes: Task 1 的 `AgentRole`、`AgentState`、`FeynmanState`、`AgentResult`。
- Produces: `EventRecord`、`MemorySnapshot`、`MemoryView`、`EventStore`、`SqlAlchemyEventStore`、`MemoryStore.load()`、`MemoryStore.view_for()`、`MemoryStore.append_event()`、`MemoryStore.find_request_result()`。

- [ ] **Step 1: 写事件归约和隔离失败测试**

```python
def test_memory_store_reduces_state_snapshot_and_agent_messages():
    store = MemoryStore(FakeEventStore([
        event("state_snapshot", metadata={
            "state": {"phase": "student_dialogue", "student_rounds": 2}
        }),
        event("agent_user_message", role="student", content="我解释了循环"),
        event("agent_message", role="student_agent", content="那边界条件呢？"),
    ]))

    snapshot = store.load(session_id=12)

    assert snapshot.state.phase == "student_dialogue"
    assert snapshot.state.student_rounds == 2
    assert snapshot.agent_messages[AgentRole.STUDENT_AGENT][-1]["content"] == "那边界条件呢？"


def test_student_memory_view_hides_bug_artifacts():
    store = MemoryStore(FakeEventStore([
        event("tool_result", role="student_agent", metadata={
            "artifact": {
                "buggy_code": "int x = 0;",
                "bugs": [{"description": "hidden"}]
            }
        })
    ]))

    view = store.view_for(store.load(12), AgentRole.STUDENT_AGENT)

    assert "buggy_code" not in json.dumps(view.to_prompt_dict(), ensure_ascii=False)
    assert "hidden" not in json.dumps(view.to_prompt_dict(), ensure_ascii=False)
```

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_memory.py -q`

Expected: FAIL，因为 `MemoryStore`、事件记录和角色投影尚未实现。

- [ ] **Step 3: 实现可注入的事件存储**

定义不依赖 Flask 的接口，生产实现只在短事务内操作 `ThinkingStageLog`：

```python
@dataclass
class EventRecord:
    session_id: int
    stage: int
    event_type: str
    role: str
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventStore(Protocol):
    def list_events(self, session_id: int, stage: int = 3) -> List[EventRecord]:
        raise NotImplementedError

    def append(self, event: EventRecord) -> EventRecord:
        raise NotImplementedError


class SqlAlchemyEventStore:
    def list_events(self, session_id: int, stage: int = 3) -> List[EventRecord]:
        logs = ThinkingStageLog.query.filter_by(
            session_id=session_id,
            stage=stage,
        ).order_by(ThinkingStageLog.created_at.asc()).all()
        return [EventRecord.from_log(log) for log in logs]
```

`MemoryStore.load()` 读取最近 10 轮可见消息、最后一个 `state_snapshot` 和代码工件索引。`view_for()` 按角色过滤内部工件，并只返回提示词需要的字段。

测试中的 `FakeEventStore` 实现同一组 `list_events()`/`append()` 方法，并以列表保存事件，生产代码不得依赖这个替身。

- [ ] **Step 4: 加入 request_id 去重和事件写入**

让 `find_request_result(session_id, request_id)` 查找 `metadata_json.request_id` 对应的已完成 `agent_message`、`tool_result` 或 `AgentResult` 快照。重复请求直接复用已有公开结果，不重新生成代码。

```python
def append_event(
    self,
    session_id: int,
    event_type: str,
    role: str,
    content: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> EventRecord:
    event = EventRecord(
        session_id=session_id,
        stage=3,
        event_type=event_type,
        role=role,
        content=content,
        metadata=metadata or {},
    )
    return self.event_store.append(event)
```

- [ ] **Step 5: 运行测试并提交 Memory 层**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_memory.py -q`

Expected: PASS；额外检查状态快照缺失、损坏 JSON、旧 `chat/write_code/fix_code` 事件和空历史都能安全降级。

```powershell
git add -- utils/agents/memory.py tests/test_stage3_agent_memory.py
git commit -m "feat: add stage3 event memory store"
```

## Task 3: 实现 StructuredDecisionModel

**Files:**
- Create: `utils/agents/model.py`
- Test: `tests/test_stage3_agent_contracts.py`

**Interfaces:**
- Consumes: Task 1 的 `AgentDecision`；现有 `services.llm_client.SharedLLMClient.chat()`。
- Produces: `DecisionModel` 协议、`ModelError`、`StructuredDecisionModel.decide()`、`parse_json_decision()` 和固定的 JSON 修复 fallback。

- [ ] **Step 1: 写模型解析失败测试**

```python
class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def is_available(self):
        return True

    def chat(self, messages, temperature=0.7, max_tokens=2000):
        self.calls.append(messages)
        return next(self.responses)


def test_structured_model_accepts_fenced_json():
    model = StructuredDecisionModel(FakeClient([
        "```json\n{\"message\":\"请解释边界\"}\n```"
    ]))

    decision = model.decide(system_prompt="system", context="context", tool_specs=[])

    assert decision.message == "请解释边界"


def test_structured_model_repairs_invalid_json_once():
    client = FakeClient(["这不是 JSON", '{"message":"修复后"}'])
    model = StructuredDecisionModel(client)

    decision = model.decide(system_prompt="system", context="context", tool_specs=[])

    assert decision.message == "修复后"
    assert len(client.calls) == 2
```

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py -q`

Expected: FAIL，因为结构化模型适配器尚未创建。

- [ ] **Step 3: 实现 provider-neutral JSON 请求**

实现以下协议，不向 `SharedLLMClient` 传递供应商专属的 `tools` 参数：

```python
class DecisionModel(Protocol):
    def decide(
        self,
        *,
        system_prompt: str,
        context: str,
        tool_specs: List[Dict[str, Any]],
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> AgentDecision:
        raise NotImplementedError
```

第一条请求包含角色规则、目标、角色记忆投影和工具 schema；工具结果以明确的 `[TOOL_RESULT]` JSON 文本追加到下一轮上下文。`parse_json_decision()` 支持裸 JSON 和单层 Markdown JSON 代码块，拒绝带额外解释的混合文本，并在进入 `AgentDecision.from_payload()` 前检查响应长度和顶层对象类型。

- [ ] **Step 4: 实现一次修复和不可用 fallback**

无效 JSON 只允许一次修复请求，修复提示必须要求“只输出符合 schema 的 JSON”。客户端不可用或两次解析失败时，返回角色配置提供的安全 `AgentDecision`，并通过公开的 `ModelError` 保留错误类型供 AgentLoop 记录；禁止把原始模型输出或异常堆栈写入 API 响应。

- [ ] **Step 5: 运行测试并提交模型层**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_contracts.py -q`

Expected: PASS；覆盖客户端不可用、空响应、未知 `ui_action`、工具参数不是对象和超过消息长度的响应。

```powershell
git add -- utils/agents/model.py tests/test_stage3_agent_contracts.py
git commit -m "feat: add structured agent decision model"
```

## Task 4: 实现 ToolRegistry 和阶段三工具

**Files:**
- Create: `utils/agents/tools.py`
- Test: `tests/test_stage3_agent_tools.py`

**Interfaces:**
- Consumes: Task 1 的 `ToolCall`、`ToolResult`、`FeynmanState`，Task 2 的 `MemorySnapshot`。
- Produces: `ToolDefinition`、`ToolContext`、`ToolRegistry.register()`、`ToolRegistry.specs_for()`、`ToolRegistry.execute()`、`build_feynman_tool_registry()`。

- [ ] **Step 1: 写权限、参数和隐藏数据失败测试**

```python
def test_student_agent_cannot_call_evaluate_fix_as_teacher():
    registry = build_feynman_tool_registry(
        buggy_code_generator=lambda context: {},
        fix_evaluator=lambda context, fixed_code: {"correct": True},
    )

    result = registry.execute(
        role=AgentRole.TEACHER_AGENT,
        call=ToolCall("c1", "evaluate_fix", {"fixed_code": "answer"}),
        context=fake_tool_context(AgentRole.TEACHER_AGENT),
    )

    assert result.ok is False
    assert result.error_code == "TOOL_NOT_ALLOWED"


def test_buggy_attempt_keeps_hidden_bugs_out_of_model_content():
    registry = build_feynman_tool_registry(
        buggy_code_generator=lambda context: {
            "buggy_code": "code",
            "bugs": [{"description": "hidden"}],
            "message": "我写了一版。",
        },
        fix_evaluator=lambda context, fixed_code: {"correct": False},
    )

    result = registry.execute(
        role=AgentRole.STUDENT_AGENT,
        call=ToolCall("c1", "generate_buggy_attempt", {}),
        context=fake_tool_context(AgentRole.STUDENT_AGENT),
    )

    assert result.public_content["buggy_code"] == "code"
    assert "hidden" not in json.dumps(result.model_content, ensure_ascii=False)
```

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_tools.py -q`

Expected: FAIL，因为工具注册表和 handler 尚未存在。

- [ ] **Step 3: 实现定义、权限和 schema 校验**

```python
ToolHandler = Callable[[ToolContext, Dict[str, Any]], ToolResult]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    allowed_roles: FrozenSet[AgentRole]
    handler: ToolHandler
    side_effect: bool = False


class ToolRegistry:
    def register(self, definition: ToolDefinition) -> None:
        self._definitions[definition.name] = definition

    def specs_for(self, role: AgentRole) -> List[Dict[str, Any]]:
        return [definition.public_spec() for definition in self._definitions.values()
                if role in definition.allowed_roles]

    def execute(self, role: AgentRole, call: ToolCall, context: ToolContext) -> ToolResult:
        definition = self._definitions.get(call.name)
        if definition is None:
            return ToolResult(ok=False, error_code="UNKNOWN_TOOL")
        if role not in definition.allowed_roles:
            return ToolResult(ok=False, error_code="TOOL_NOT_ALLOWED")
        if not self._arguments_match_schema(definition.input_schema, call.arguments):
            return ToolResult(ok=False, error_code="INVALID_TOOL_ARGUMENTS")
        if definition.side_effect and self._already_executed(context, call.call_id):
            return self._cached_result(context, call.call_id)
        return definition.handler(context, call.arguments)
```

参数校验只接受定义中列出的字段，拒绝未知字段和过长字符串；副作用工具的 `call_id` 在当前请求中只能执行一次。未知工具、越权和 schema 错误必须返回结构化 `ToolResult`，不能抛出未处理的 `KeyError`。

- [ ] **Step 4: 实现六个阶段三工具**

工具行为固定如下：

```text
inspect_learning_state   -> 返回公开阶段、关键概念和学习证据
recall_memory            -> 返回当前角色可见的历史摘要
record_learning_evidence -> 校验 concept/evidence 并生成 state_patch
generate_buggy_attempt   -> 调用注入的生成器，bugs 只写内部事件，代码放 public_content
evaluate_fix             -> 调用注入的评估器，返回 correct/feedback，不返回 hidden bugs
complete_goal            -> 仅在证据、阶段和代码审查条件满足时设置完成请求
```

默认 callback 适配现有 `utils.thinking_ai.student_agent_write_code()` 和 `evaluate_feynman_code_fix()`；测试通过 lambda 注入，避免真实 LLM。

- [ ] **Step 5: 运行测试并提交工具层**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_tools.py -q`

Expected: PASS；覆盖未知工具、越权调用、参数错误、重复 call id、生成失败和评估失败。

```powershell
git add -- utils/agents/tools.py tests/test_stage3_agent_tools.py
git commit -m "feat: add stage3 agent tool registry"
```

## Task 5: 实现有限步数 AgentLoop

**Files:**
- Create: `utils/agents/loop.py`
- Test: `tests/test_stage3_agent_loop.py`

**Interfaces:**
- Consumes: Task 1 的合同、Task 2 的 `MemoryStore`、Task 3 的 `DecisionModel`、Task 4 的 `ToolRegistry`。
- Produces: `AgentLoopConfig`、`AgentLoop`、`AgentLoop.handle_turn()`。

- [ ] **Step 1: 写 direct response、tool chain 和 max-step 失败测试**

```python
def test_agent_loop_executes_tool_then_uses_result():
    model = FakeDecisionModel([
        AgentDecision(tool_calls=[ToolCall("c1", "inspect_learning_state", {})]),
        AgentDecision(message="根据状态，我们先讨论循环边界。"),
    ])
    tools = FakeRegistry({"inspect_learning_state": ToolResult(
        ok=True,
        model_content={"focus": "循环边界"},
    )})
    loop = make_loop(model=model, tools=tools)

    result = loop.handle_turn("我不知道怎么判断结束", request_id="r1")

    assert result.response == "根据状态，我们先讨论循环边界。"
    assert tools.calls == [(AgentRole.TEACHER_AGENT, "inspect_learning_state")]


def test_agent_loop_stops_after_four_model_decisions():
    model = FakeDecisionModel([
        AgentDecision(tool_calls=[ToolCall(str(i), "inspect_learning_state", {})])
        for i in range(5)
    ])

    result = make_loop(model=model).handle_turn("继续", request_id="r2")

    assert result.success is False
    assert result.error_code == "MAX_AGENT_STEPS"
```

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py -q`

Expected: FAIL，因为 AgentLoop 尚未实现。

- [ ] **Step 3: 实现请求生命周期和事件写入**

`handle_turn()` 采用以下签名：

```python
def handle_turn(
    self,
    user_message: str,
    *,
    request_id: str,
    input_kind: str = "chat",
) -> AgentResult:
    raise NotImplementedError
```

先通过 `MemoryStore.find_request_result()` 去重，再在 session 锁内追加 `agent_user_message`。每次模型响应写入 `agent_decision`；每次工具执行写入 `tool_call` 和 `tool_result`；最终写入 `agent_message` 与 `state_snapshot`。模型调用期间不持有数据库事务，提交事件时重新打开短事务。

- [ ] **Step 4: 实现工具循环、错误处理和完成校验**

```python
context = ToolContext(
    session_id=self.session_id,
    request_id=request_id,
    role=self.role,
    memory=self.memory.load(self.session_id),
)
tool_results = []
for step in range(self.config.max_model_steps):
    decision = self.model.decide(
        system_prompt=self.spec.system_prompt,
        context=self._build_context(input_kind=input_kind),
        tool_specs=self.tools.specs_for(self.role),
        tool_results=tool_results,
    )
    self.memory.append_event(
        self.session_id,
        "agent_decision",
        self.role.value,
        content=decision.message,
        metadata={"request_id": request_id, "decision": decision.to_payload()},
    )
    if not decision.tool_calls:
        return self._finish_public_response(decision)
    for call in decision.tool_calls:
        result = self.tools.execute(self.role, call, context)
        self._persist_tool_result(call, result)
        tool_results.append(result.to_model_dict())
        self._apply_state_patch(result.state_patch)
        if result.public_content.get("ui_action") == "show_code_review":
            return self._finish_code_review(result)
raise AgentLoopError("MAX_AGENT_STEPS")
```

只读工具错误可以重试一次；副作用工具错误直接返回结构化失败。模型提出 `goal_status=achieved` 时必须经过 `complete_goal` 的服务端校验，不能直接设置 `ThinkingSession.status`。

- [ ] **Step 5: 运行测试并提交循环层**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py -q`

Expected: PASS；覆盖直接回复、连续工具、未知工具、无效决策 fallback、工具失败、最大步数和 request id 重复请求。

```powershell
git add -- utils/agents/loop.py tests/test_stage3_agent_loop.py
git commit -m "feat: add bounded stage3 agent loop"
```

## Task 6: 装配 Teacher/Student Feynman Runtime

**Files:**
- Create: `utils/agents/feynman.py`
- Modify: `utils/agents/__init__.py`
- Test: `tests/test_stage3_agent_loop.py`

**Interfaces:**
- Consumes: Task 1-5 的所有公开接口，以及 `Assignment`、`AssignmentThinkingPreset`、`ThinkingSession`。
- Produces: `AgentSpec`、`build_feynman_runtime()`、`DualFeynmanRuntime.handle_chat()`、`DualFeynmanRuntime.generate_buggy_attempt()`、`DualFeynmanRuntime.evaluate_fix()`。

- [ ] **Step 1: 写两个角色的可见上下文和转换失败测试**

```python
def test_student_runtime_exposes_student_goal_but_not_reference_code():
    runtime = make_feynman_runtime(fake_model=FakeDecisionModel([
        AgentDecision(message="你能解释一下输入范围吗？")
    ]))

    runtime.handle_chat(
        AgentRole.STUDENT_AGENT,
        "我先读入数据",
        request_id="r-student-1",
    )

    context = runtime.model.calls[0]["context"]
    assert "teach_and_repair" in context
    assert "标准答案" not in context


# FakeDecisionModel 记录每次 decide() 的 system_prompt、context、tool_specs
# 和 tool_results 到 calls，make_feynman_runtime() 使用内存事件存储和测试会话。


def test_successful_fix_marks_session_completed_only_after_evaluation():
    runtime = make_feynman_runtime(
        fix_evaluator=lambda context, fixed_code: {
            "correct": True,
            "feedback": "修复正确",
        }
    )

    result = runtime.evaluate_fix("fixed code", request_id="r-fix-1")

    assert result.public_content["correct"] is True
    assert runtime.session.status == "completed"
```

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py -q -k feynman`

Expected: FAIL，因为角色配置和 runtime factory 尚未存在。

- [ ] **Step 3: 实现 AgentSpec 和角色提示**

定义两个角色的固定目标和允许工具，不把标准答案原文放进 Student Agent 的 context：

```python
@dataclass(frozen=True)
class AgentSpec:
    role: AgentRole
    goal: str
    system_prompt: str
    fallback_message: str
    max_output_chars: int = 1200


def build_feynman_runtime(session, assignment, preset, *, model=None, callbacks=None):
    return DualFeynmanRuntime(
        session=session,
        assignment=assignment,
        preset=preset,
        model=model or StructuredDecisionModel(),
        callbacks=callbacks or FeynmanCallbacks(),
    )
```

Teacher Agent 的公开上下文包含阶段一描述、阶段二完成状态和可见学习证据；Student Agent 只包含题目描述、关键概念摘要、用户解释和角色记忆视图。

- [ ] **Step 4: 接入代码生成、修复评估和会话状态**

`generate_buggy_attempt()` 强制通过 Student Agent 的 `generate_buggy_attempt` 工具，完整 `bugs` 写入 `tool_result.metadata`，公开返回 `buggy_code` 和 `message`。`evaluate_fix()` 忽略请求体中传入的 `buggy_code`，从最后一个内部工件读取隐藏 Bug；评估正确时更新 `stage3_completed/status/completed_at` 并写入 `stage_pass`。

- [ ] **Step 5: 运行测试并提交 runtime 层**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_loop.py -q -k feynman`

Expected: PASS；确认两种角色的上下文隔离、代码审查转换、错误评估不推进状态和修复成功才完成会话。

```powershell
git add -- utils/agents/__init__.py utils/agents/feynman.py tests/test_stage3_agent_loop.py
git commit -m "feat: assemble feynman dual-agent runtime"
```

## Task 7: 把阶段三 Flask 路由切换到 Runtime

**Files:**
- Modify: `routes/thinking.py:15-21,174-211,688-921,1110-1122`
- Create: `tests/test_stage3_agent_routes.py`

**Interfaces:**
- Consumes: `build_feynman_runtime()` 及其 `handle_chat/generate_buggy_attempt/evaluate_fix`。
- Produces: 现有四个阶段三端点的兼容行为；新请求接受 `message`、`request_id`，旧 `messages` 仍可作为 fallback。

- [ ] **Step 1: 写路由失败测试**

先在 `tests/test_stage3_agent_routes.py` 添加可复用的 SQLite fixture。它沿用 `tests/test_app.py` 的 `create_app('testing')` 方式，创建登录学生、作业、就绪预设和当前阶段三会话：

```python
@pytest.fixture
def stage3_context(tmp_path):
    app = create_app("testing")
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'stage3.db'}",
    )
    with app.app_context():
        db.create_all()
        student = User(student_id="student-1", username="student-1", usertype="学生")
        student.password = "password"
        assignment = Assignment(
            title="循环练习",
            description="解释循环边界并修复错误代码",
            creator_id="student-1",
        )
        preset = AssignmentThinkingPreset(
            assignment=assignment,
            reference_code="int main() { return 0; }",
            key_steps=json.dumps(["输入", "循环边界", "输出"], ensure_ascii=False),
            difficulty_config=json.dumps({"feynman_rounds": 3}),
            status="ready",
        )
        session = ThinkingSession(
            student=student,
            assignment=assignment,
            current_stage=3,
            stage2_completed=True,
        )
        db.session.add_all([student, assignment, preset, session])
        db.session.commit()
        session_id = session.id

    client = app.test_client()
    client.post("/login", data={"username": "student-1", "password": "password"})
    return client, session_id


def test_stage3_chat_uses_current_message_not_client_history(stage3_context, monkeypatch):
    client, session_id = stage3_context
    fake_runtime = FakeRuntime(chat_result=AgentResult(
        success=True,
        agent=AgentRole.TEACHER_AGENT,
        response="请解释边界。",
        ui_action=UIAction.CONTINUE_CHAT,
    ))
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: fake_runtime)

    response = client.post("/thinking/api/stage3/chat", json={
        "session_id": session_id,
        "message": "当前消息",
        "messages": [{"role": "user", "content": "篡改历史"}],
        "request_id": "route-r1",
    })

    assert response.status_code == 200
    assert fake_runtime.chat_messages == [(AgentRole.TEACHER_AGENT, "当前消息", "route-r1")]


def test_fix_code_ignores_client_buggy_code_and_returns_feedback(stage3_context, monkeypatch):
    client, session_id = stage3_context
    fake_runtime = FakeRuntime(fix_result=AgentResult(
        success=True,
        agent=AgentRole.STUDENT_AGENT,
        public_content={"correct": False, "feedback": "还需要检查边界。"},
    ))
    monkeypatch.setattr(thinking_routes, "build_feynman_runtime", lambda *args, **kwargs: fake_runtime)

    response = client.post("/thinking/api/stage3/fix_code", json={
        "session_id": session_id,
        "buggy_code": "伪造的代码",
        "fixed_code": "用户提交的修复",
        "request_id": "route-fix-1",
    })

    assert response.json["correct"] is False
    assert fake_runtime.fixed_codes == [("用户提交的修复", "route-fix-1")]
```

测试文件顶部同时定义 `FakeRuntime`：构造函数接收 `chat_result` 和 `fix_result` 两个 `AgentResult`，保存 `chat_messages` 和 `fixed_codes`；`handle_chat()` 记录 `(role, message, request_id)` 后返回 `chat_result`，`evaluate_fix()` 记录 `(fixed_code, request_id)` 后返回 `fix_result`。测试文件导入 `AgentResult`、`AgentRole`、`UIAction`，路由统一调用 `to_public_dict()`。这样测试可以验证路由传入的是当前消息和 `fixed_code`，而不是信任客户端历史或客户端 `buggy_code`。

同一测试文件还要覆盖三条持久化边界：`write_code` 的响应只能包含 `buggy_code/message`，但数据库 `tool_result` 事件必须保存完整隐藏 `bugs`；相同 `request_id` 重试时只返回第一次公开结果且不新增事件；另一个登录用户访问该 `session_id` 必须返回 403。再补一条只提交旧 `messages` 的请求，确认服务端仍能提取最后一条用户消息。

- [ ] **Step 2: 运行失败测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_routes.py -q`

Expected: FAIL，因为路由仍然调用旧的 `teacher_agent_chat/student_agent_chat`，也没有新的 runtime fixture。

- [ ] **Step 3: 添加消息提取和 session 归属校验**

在 `routes/thinking.py` 增加两个小 helper：

```python
def _extract_stage3_message(data: dict) -> str:
    message = (data.get("message") or "").strip()
    if message:
        return message
    for item in reversed(data.get("messages") or []):
        if item.get("role") == "user":
            return str(item.get("content") or "").strip()
    return ""


def _request_id(data: dict) -> str:
    value = str(data.get("request_id") or "").strip()
    return value[:80] if value else uuid.uuid4().hex
```

缺少消息返回 400；旧 `student_state` 不再进入模型上下文；`session_id` 必须属于当前登录用户。

- [ ] **Step 4: 改造四个端点和恢复历史**

`stage3_teacher_chat` 和 `stage3_student_teach` 只调用 `runtime.handle_chat()`；保留现有最少 5 字和高相似度拦截，但历史读取改为 MemoryStore 的阶段三事件。

`stage3_write_code` 调用 `runtime.generate_buggy_attempt()`，返回 `buggy_code/message/ui_action`，并确保 `bugs` 完整写入内部事件。`stage3_fix_code` 调用 `runtime.evaluate_fix(fixed_code, request_id)`，不信任请求体的 `buggy_code`。

`start_session()` 的历史恢复逻辑同时识别旧事件和新事件：

```text
chat / agent_user_message -> user message
chat / agent_message      -> assistant message
write_code / tool_result  -> code review artifact + assistant message
fix_code                  -> submitted fix message
```

- [ ] **Step 5: 运行路由测试并提交服务端接入**

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_routes.py -q`

Expected: PASS；额外检查未登录 302/401 行为、跨用户 session 403、重复 request id 不生成第二个 `ThinkingStageLog`、旧 `messages` 请求仍能工作。

```powershell
git add -- routes/thinking.py tests/test_stage3_agent_routes.py
git commit -m "feat: route stage3 through agent runtime"
```

## Task 8: 更新阶段三前端请求协议

**Files:**
- Modify: `static/js/thinking.js:1047-1219`

**Interfaces:**
- Consumes: 现有阶段三 API 的 `response`、`ui_action`、`ready_for_code`、`buggy_code`、`feedback`。
- Produces: 当前消息 + `request_id` 请求；保留本地数组只做 UI 渲染，不作为服务端状态来源。

- [ ] **Step 1: 先确认当前页面契约**

检查 `sendTeacherChat()`、`sendStudentChat()`、`triggerCodeWritingPhase()` 和 `submitCodeFix()` 当前 payload，确认每个函数只依赖对应端点的公开字段。

Run: `Select-String -LiteralPath 'static/js/thinking.js' -Pattern 'stage3/chat|stage3/teach|stage3/write_code|stage3/fix_code|messages'`

Expected: 输出 4 个阶段三端点和当前数组传参位置，作为修改前记录。

- [ ] **Step 2: 修改聊天请求并生成 request id**

给每次发送生成稳定 id：

```javascript
function newAgentRequestId(prefix) {
    if (window.crypto && window.crypto.randomUUID) {
        return `${prefix}-${window.crypto.randomUUID()}`;
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
```

聊天请求只发送：

```javascript
body: JSON.stringify({
    session_id: state.sessionId,
    message,
    request_id: newAgentRequestId('teacher')
})
```

Student 请求同样只提交当前消息；保留 `state.teacherMessages/studentMessages` 用于即时渲染和旧页面恢复。

- [ ] **Step 3: 处理 UI action 和代码工件**

`sendStudentChat()` 根据 `data.ui_action === 'show_code_review'` 或兼容字段 `data.ready_for_code` 进入代码审查；`triggerCodeWritingPhase()` 不再提交完整历史，只提交 `session_id` 和新的 request id；`submitCodeFix()` 不再提交 `buggy_code`，只提交 `fixed_code`。

- [ ] **Step 4: 运行前端语法和后端回归检查**

Run: `node --check static/js/thinking.js`

Expected: exit code 0。若系统没有 `node`，使用项目可用的 Node runtime 执行同一检查，并记录替代命令。

Run: `& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_agent_routes.py tests/test_stage3_agent_loop.py -q`

Expected: PASS。

- [ ] **Step 5: 提交前端协议改动**

```powershell
git add -- static/js/thinking.js
git commit -m "feat: send stage3 agent turns from frontend"
```

## Task 9: 完成回归验证并整理交付信息

**Files:**
- Modify: 无业务文件；只检查前面任务的提交和工作区。
- Test: `tests/test_stage3_agent_contracts.py`、`tests/test_stage3_agent_memory.py`、`tests/test_stage3_agent_tools.py`、`tests/test_stage3_agent_loop.py`、`tests/test_stage3_agent_routes.py`、`tests/`。

**Interfaces:**
- Consumes: 前面所有任务的公开接口。
- Produces: 可复现的验证结果、未跟踪文件审计和最终变更摘要。

- [ ] **Step 1: 运行新功能测试**

Run:

```powershell
& 'E:\anaconda\python.exe' -m pytest `
  tests/test_stage3_agent_contracts.py `
  tests/test_stage3_agent_memory.py `
  tests/test_stage3_agent_tools.py `
  tests/test_stage3_agent_loop.py `
  tests/test_stage3_agent_routes.py -q
```

Expected: 全部 PASS。

- [ ] **Step 2: 运行项目回归测试**

Run: `& 'E:\anaconda\python.exe' -m pytest tests -q`

Expected: 现有 355 个基线测试加新测试全部通过；允许已有 DeprecationWarning，但不能新增未处理异常。

- [ ] **Step 3: 检查完整工作区和提交内容**

```powershell
git status --short
git diff HEAD~1 --stat
git log -8 --oneline
```

确认提交只包含 AgentLoop 相关文件，工作区已有的研究、输出和临时文件保持未暂存。

- [ ] **Step 4: 运行无 API Key 冒烟流程**

使用 Fake Model 启动一个测试 `ThinkingSession`，依次执行 Teacher 聊天、Student 教学、生成错误代码和错误修复；确认模型不可用时返回安全文本、事件不推进阶段，正确修复才设置 `status='completed'`。

- [ ] **Step 5: 记录最终验证结果**

在最终交付中报告：新测试数量、`pytest tests` 结果、前端语法检查结果、基线收集限制，以及是否保留任何已知兼容限制。只有验证命令实际通过后，才声明功能完成。
