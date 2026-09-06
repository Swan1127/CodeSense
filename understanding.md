# CodeSense 项目综合理解文档（understanding）

> 定位：本文是一份**独立的综合理解文档**，基于对工作区源码的逐步静态阅读（覆盖入口/配置、路由、服务、工具、Agent、后台任务、前端模板与 JS、测试与文档），并按要求**整合了个人学习记录（`project-understanding_wjh.md`）中的运行验证、使用中发现的问题与个人理解/设想**。文中的机制性结论不重复堆砌个人笔记式表述，按统一口径标注证据强度。
>
> 结论标注约定：**【源码确认】**＝依据工作区源码静态核对（个人记录声明其与固定「源码核对基线」提交 `22f93d4` 无代码差异，仅文档自身有修订），标注中给出对应源码位置；**【源码推断】**＝仅由调用关系或注释推断、未逐行核实；**【运行验证】**＝整合自 `project-understanding_wjh.md` 附录 B 的实际运行/测试记录（本会话未重复执行），引用其范围澄清结论。未附「运行验证」字样的机制断言均属源码静态分析，不声称已被实跑确认。
>
> 配套说明（面向文档型 PR 评审）：本 PR 无业务代码、生产配置或密钥变更；PR 描述的「AI 使用说明、查阅文件、验证命令、未解决问题」分别对应文首约定、附录 C 查阅文件清单、附录 B 引用的验证命令与第五节「风险与疑问」。

---

## 一、项目定位

CodeSense（酷森思）是面向高校编程教学的 AI 辅助评测与学习平台：把**代码提交、受限执行（Causal Sandbox）、AI 启发式辅导、分阶段练习、学情分析**放进同一条学习链路。核心定位是**引导学生自己学会，而不是替学生写出答案**。

### 主要用户
1. 学生：提交 C++ 程序、查看测试结果与反馈，进入三阶段引导式学习流程，记录自己的思路与解释。
2. 教师：创建/管理作业，组织班级与花名册，查看提交记录、知识点与能力趋势。
3. 开发者/研究者：在 Flask、SQLAlchemy 与可替换的 AI 服务接口上扩展评测、教学与数据分析能力。

### 要解决的核心问题
- **对学生的痛点**：传统 OJ 只给「对/错」二元结果，学生无法定位问题在思路、实现、边界还是调试。CodeSense 以受限评测 + AI 辅导 + 「思路描述 → 步骤组装 → 费曼讲解」三阶段，把「理解」过程变得可见、可评估。
- **对教师的痛点**：反馈零散、共性问题难发现。CodeSense 用**两层画像体系**沉淀学情：一层是可量化的 C 知识点画像（0–100，贝叶斯权重更新至 `KnowledgePointScore`），一层是 AI 生成的文本能力分析（存于 `AbilityTrend`），教师据此做可统计、可下钻的学情视图。

### 技术边界
- 语言：Python（Flask 2.2.3 单体应用）+ Jinja2 模板 + 原生 JS；评测对象为 **C/C++**（沙箱 g++ C++17）。
- AI：可替换 provider（智谱/OpenAI），支持无本地模型（纯 AI-only）运行。

---

## 二、总体结构与模块分层

分层思路：**routes（薄）→ services（厚，偏业务纯逻辑）→ utils（引擎/工具）→ models（单文件 ORM）**，后台任务与前端独立成层。

### 顶层文件（入口与配置）
| 文件 | 职责 |
|---|---|
| [app.py](file:///d:/MyCodesence/CodeSense/app.py) | 应用工厂 `create_app()`：注册 Blueprint、初始化 DB/会话/登录态、ProxyFix、后台任务、访问日志与压缩中间件；全局 `before_request` |
| [config.py](file:///d:/MyCodesence/CodeSense/config.py) | development / testing / production 三套配置；production 强制 DATABASE_URL 与 SECRET_KEY≥32、`DB_AUTO_INIT=False` |
| [wsgi.py](file:///d:/MyCodesence/CodeSense/wsgi.py) | 生产 WSGI 入口（默认强制 production）；[run.py](file:///d:/MyCodesence/CodeSense/run.py) 本地开发入口 |
| [models.py](file:///d:/MyCodesence/CodeSense/models.py) | 全部 ORM 模型单文件（含 18 个数据表模型 + 会话存储类，合计 19 个 class） |
| [forms.py](file:///d:/MyCodesence/CodeSense/forms.py) | Flask-WTF 表单定义 |
| [database_maintenance.py](file:///d:/MyCodesence/CodeSense/database_maintenance.py) | 生产一次性建表/补列/建索引维护脚本 |
| [deploy.sh](file:///d:/MyCodesence/CodeSense/deploy.sh) / [update.sh](file:///d:/MyCodesence/CodeSense/update.sh) | 首次部署 / git pull + 重启 systemd |

### routes/ — 8 个 Blueprint
`auth.py`（登录/注册/演示登录/邀请）、`main.py`（首页/看板/导出/调试）、`assignments.py`（作业/测试用例/提交评测页）、`thinking.py`（三阶段引导式学习与阶段 Agent API，2432 行，最大路由）、`classes.py`（班级/花名册）、`users.py`（用户管理）、`grades.py`（成绩册/Excel 导出）、`api.py`（提交/AI 建议/能力分析 SSE，1612 行）。

### services/ — 业务服务层
`llm_client.py`（`SharedLLMClient` 统一 LLM 客户端）、`ai_evaluator.py`（AI 评测/流式能力分析）、`api_keys.py`（密钥管理）、`course_grading.py`、`teacher_analytics.py`、`teacher_ai_advisor.py`、`demo_database.py` / `demo_experience.py`（公开体验隔离与演示数据）。

### utils/ — 引擎与工具层
`sandbox_runner.py`（沙箱）、`code_evaluator.py`（启发式+可选 LLM）、`llm_evaluator.py`（**旧版** LLM 评估器，见三.7）、`guidance_generator.py`、`code_advisor.py`、`ability_scorer.py`/`maturity_calculator.py`、`async_tasks.py`/`sse.py`、`thinking_ai.py`、`markdown_formatter.py`、`prompts.py`、`auth.py`/`api.py`/`validate_testcases.py`；以及 **`utils/agents/`**：费曼/论坛 Agent 子系统（`feynman.py`/`loop.py`/`tools.py`/`model.py`/`orchestrator.py`/`intent.py`/`memory.py`/`coverage.py`/`goal.py`/`contracts.py`）。

### tasks/ 与前端
- `tasks/submission_tasks.py`（提交评测后台链）、`tasks/ability_analysis.py`（能力画像异步计算）。
- `templates/`：Jinja2 页面（角色区分首页/详情页 + `thinking/arena.html` 三阶段竞技场）；`static/`：JS（SSE 客户端、Monaco 按需加载、编辑器/提交/思路对话脚本、安全输出处理器）与 CSS/图片/第三方库。
- `tests/`：pytest，覆盖沙箱演示特性、演示隔离（`test_demo_*`）、阶段三 Agent/论坛、SSE、成绩、班级、HTTPS 代理、性能基线及沙箱输出有界进程测试。

### 核心数据模型一览
- 用户与组织：`User`（学生/教师/管理员）、`Class`、`StudentRoster`、`InviteToken`
- 教学资源：`Assignment`、`AssignmentKnowledgePoint`、`TestCase`、`AssignmentThinkingPreset`
- 学习记录：`Submission`、`ThinkingSession`、`ThinkingStageLog`、`StudentQuestion`、`CodeAdviceRequest`
- 画像与学情：`AbilityTrend`、`KnowledgePointScore`、`TeacherAISuggestion`
- 平台支撑：`SystemLog`、`SystemConfig`、`CodeSenseSession`（动态绑定会话存储类）

---

## 三、核心机制与运行流程

### 1. 应用启动与请求生命周期（源码确认）
`create_app()` 依次完成：加载 config → 配置连接池与 Session（优先 Redis、失败降级文件系统）→ 初始化 db/Flask-Login/Flask-Session → 注册 8 蓝图 → 初始化异步任务系统 →（development）自动建表。全局 `before_request` 做两件事：**单点登录校验** 与 **演示临时库激活**。附带中间件：gzip 压缩、响应/慢请求日志、`/healthz` `/readyz` 探针、ProxyFix 反代协议还原。

### 2. 双重会话体系与单点登录（源码确认）
系统同时存在两套登录状态：历史遗留的 `session['usertype']` 等键 + 现代 Flask-Login `current_user`。单点登录靠 `user.current_session_id` 与 `session['current_session_id']` 比对，由 `before_request` 强制执行。**双体系并存是大量权限/一致性 Bug 的根因**（见第五节）。登录路径：普通登录、演示登录（`/demo-login/<role>`，写入 `session[DEMO_SESSION_KEY]` 后播种）、`/sandbox-login/<student_id>` 免密登入、教师邀请 token 注册。

### 3. 代码提交 → 评测调用链（源码确认，最重要链路）
两条平行通路：

**A. 网页表单路径（异步，主流）**：`POST /submit/<assignment_id>`（[routes/assignments.py](file:///d:/MyCodesence/CodeSense/routes/assignments.py)）创建 `Submission(status=pending)` → 投递后台线程 [tasks/submission_tasks.py](file:///d:/MyCodesence/CodeSense/tasks/submission_tasks.py)::`evaluate_submission_async` → 页面跳「评测中」，前端轮询/SSE 进度。后台按序执行：
1. AI 基础评估：启发式评分（归一 0–5）+ 可选 LLM 叠加；任务层 `_normalise_score` 兜底归一 0–5；
2. 沙箱用例评判：编译（15s 超时）→ 逐用例运行（5s 超时）→ 写回 `sandbox_passed/total/detail`；有用例时按通过率重算最终分；
3. 状态置 evaluated 并基于全量历史重算作业/用户统计；
4. 知识点画像 `update_score`；
5. 能力分析触发：`AbilityTrend.mark_as_outdated` + `trigger_analysis_if_needed()`（按键去重防并发）；
6. 写 `SystemLog`（公开体验会话不写正式库审计日志）。

**B. API 路径（同步）**：`POST /api/submit`（[routes/api.py](file:///d:/MyCodesence/CodeSense/routes/api.py)）同步评测并直接返回 JSON。

**沙箱细节（源码确认）**：`g++ -std=c++17 -O2 -Wall`；编译 15s / 运行 5s 超时；stdout/stderr 经 `_BoundedPipeReader` **有界读取各 4096 字节**，超限立即终止进程，不视为正常结束；用例结果带 `termination_reason`（`stdout_limit`/`stderr_limit`/`timeout`/`runtime_error` 等），输出经 `_normalize_output` 标准化后比对。（旧版曾依赖 CodeBERT/TextCNN 本地模型，当前 main 已移除，仅见于历史文档。）

### 4. 三阶段引导式学习（源码确认）
入口 `GET /thinking/<assignment_id>` → `templates/thinking/arena.html`：
- **初始化**：`start_session` 创建 `ThinkingSession` 并装载 `AssignmentThinkingPreset`；无预设时 AI 生成并 lazy 回填。
- **阶段一（思路）**：描述 ≥5 字符 → `evaluate_description`（本地快速检查 + 必要时 AI）按 key_steps 打分，≥50 放行，逐条写 `ThinkingStageLog`。
- **阶段二（组装）**：`verify` 用 `check_quiz_equivalence` 校验作答等价性，通过后把步骤组装规整为**可编译代码预览**并注入阶段三初始提示；AI 回复统一经 `thinking_ai.py::sanitize_response` 做**物理级代码过滤**（连续代码行会被删除替换，作为提示词之外的第二层防泄漏）。
- **阶段三（费曼双 Agent）**：`forum/message` → `utils/agents/orchestrator.py` 意图路由 + 学生/教师角色仲裁 + AgentLoop 多轮 + coverage 掌握度判定 + SSE 流式返回；`forum/trace` 轨迹复盘；`fix_code` 判定 `correct=True` 时由 runtime 写入**已校验的 `stage_pass`** 并置 `completed`；`complete_session` 仅在通过 `/server-verify` 校验后才接受（否则 409）。

### 5. 能力画像与教师端学情（源码确认）
评测成功后（两通路一致）触发：`mark_as_outdated` → `trigger_analysis_if_needed()`（防并发）→ 后台线程 `generate_ability_analysis_async` → 拉最近约 20 条提交 → `AIEvaluator.analyze_ability_trend_stream` → 前端 `/api/stream/ability-analysis`（SSE）流式渲染 Markdown → 结果落回 `AbilityTrend`。教师端经 `teacher_analytics` / `teacher_ai_advisor` 做班级/知识点聚合与建议。

### 6. 公开演示体验隔离（重点设计，源码确认）
不注册真实账号即可体验：每次进入体验入口生成带随机 run_id 的**独立临时 SQLite**；`CodeSenseSession`（继承 FlaskSQLAlchemySession）重写 `get_bind()`，按 `_codesense_demo_bind` 在**请求级**切换数据库引擎；demo_run_id 沿提交/沙箱/能力分析各后台线程传递，线程执行前二次校验会话存活；空闲 1h / 最长 2h 清理；**绝不回退正式库**。演示账号（`demo:*`）走独立 user_loader。与 AGENTS.md 的 PR worktree 数据隔离约定同源。

### 7. AI 服务抽象与新旧两层现状（源码确认）
- **新链路**（三阶段对话、能力分析、教师建议）直接使用 `services/llm_client.py::SharedLLMClient`：多 provider 重试/限流/熔断/并发信号量/singleflight/故障切换/前后台优先级集中于此。
- **旧链路**（提交评测的 LLM 叠加）仍先经 `utils/llm_evaluator.py::LLMEvaluator`：其 `_init_client` **仍自行初始化 ZhipuAI/OpenAI 客户端并选 api_type**，仅实际发请求的 `_chat_completions_create` 委托给 `SharedLLMClient`。故准确表述是：**实际网络请求统一委托 SharedLLMClient，但旧评估器的初始化/选型逻辑未收敛**。
- 已知失效点：后台任务线程因命名方式绕过了前台/后台优先级；`chat_stream` 不走 singleflight。

### 8. SSE 协议与前端（源码确认）
统一 SSE 协议 `type: start/delta/status/done(error)/error`，前端统一入口 [static/js/sse-client.js](file:///d:/MyCodesence/CodeSense/static/js/sse-client.js)（`consumeSSE`）。代码编辑器降级链：**Monaco（多 CDN 源轮询）→ CodeMirror 5.65.2 → textarea**，编辑器内容实时回写 textarea。

---

## 四、运行验证（整合自 wjh 运行记录）

> 本会话未实际运行；以下为**整合 `project-understanding_wjh.md` 附录 B** 的记录与范围澄清（原文作者：wjh，环境 Windows + Python 3.11 + g++ 16.1.0/MSYS2；时间 2026-09-03，2026-09-05 补充真实编译验证并复核新版沙箱引擎）。

### 安装与启动
- `py -3.11 -m venv .venv` + 阿里云镜像安装依赖（60 个包，Flask 2.2.3 / SQLAlchemy 2.0.52）；安装 MSYS2 g++ 16.1.0。
- **Python 3.14 不兼容**：`ast.Str` 自 3.8 弃用、3.14 移除，而 Werkzeug 2.2.3 `werkzeug/routing/rules.py` 仍使用它，启动即报 `AttributeError: module 'ast' has no attribute 'Str'`（已在本机 3.14 复现）。有效版本范围约 3.8–3.13。
- `.env` 残留 MySQL 配置会令启动连接被拒（WinError 10061），注释后回退本地 SQLite。
- `python run.py` 启动成功；本机无 Redis，会话自动降级文件系统；登录页提供学生/教师体验入口。

### 测试结果
- `tests/test_sandbox_features.py`：3 passed（演示数据装载 / 免密登录 / 生产禁用沙箱）——**不调用 g++**。
- `tests/test_sandbox_output_limits.py`（上游新增，mock 编译器，用 Python 子进程验证有界行为）：5 passed。
- `tests/test_demo_*` 隔离用例**未复跑**。

### 真实 C++ 链路验证
直接调用 `utils/sandbox_runner.run_test_cases`，g++ 编译 C++17 加法程序运行 3 用例（含隐藏用例）：`compile_success=true`，`passed 3/3`，各例 `termination_reason=null`，单例 31–186ms。覆盖**引擎层**编译→运行→标准化比对→判定。

### 范围澄清（原文关键结论）
正文「AI 实际网络请求统一委托 SharedLLMClient」「公开体验绝不写正式库」等**源码确认**结论未经真实 AI 密钥触发与 `test_demo_*` 实跑验证；Web 端完整提交评测链路（含 LLM 叠加）不在已验证范围内。读者勿将源码确认视作已实跑确认。

---

## 五、风险与疑问（Bug 清单与未决问题）

### A. 代码级风险（静态阅读发现，按严重度）
1. **未认证端点（高危）**：`/api/assignments/<id>/testcases/batch`（[routes/assignments.py](file:///d:/MyCodesence/CodeSense/routes/assignments.py)）无任何鉴权。
2. **会话信息泄露（高危）**：`/debug_session`（[routes/main.py](file:///d:/MyCodesence/CodeSense/routes/main.py)）未认证即可 dump 整个 session。
3. **错误的会话键（高危）**：`/api/submission/<submission_id>` 读取 `user_type`（正确键为 `usertype`），鉴权可能被绕过/误判。
4. **越权访问**：教师可跨班级查看学生提交详情而不校验班级归属（[routes/users.py](file:///d:/MyCodesence/CodeSense/routes/users.py)，对比 grades 的 `_accessible_classes`）；`/api/stats` 对所有教师公开全局班级数据（类级数据泄漏）。
5. **硬编码兜底密码**：`utils/auth.py` 内 `ADMIN_PASSWORD='admin123'` 兜底（生产风险）。
6. **GET 执行写操作**：`delete_user`、logout、`invite-teacher` 等多以 GET 触发删除/副作用。
7. **CSRF 大面积缺失**：多数自定义表单无 CSRF；seed 机制每次请求重新生成 token，造成连续提交不一致。
8. **注入/兼容面**：`markdown_formatter.render_html` 未转义；`utils/api.py` ASCII 回退会破坏中文。
9. **Agent 子系统卫生问题**：`_SESSION_LOCKS` 无界增长；跨模块私有导入（feynman ↔ coverage）；`AgentLoopConfig.max_model_steps` 被收紧为 4（防失控但可能截断对话）；残留死字段（`misconceptions`/`feynman_rounds`）。
10. **前端/模板技术债**：多个占位空 JS（`editor-manager.js` 等）；`styles1.css` 含乱码与嵌套 `<script>`；个别过期模板（`class_comparison` 损坏 tag、profile 硬编码假图表）。
11. **代码重复与死代码**：改密逻辑重复、存在死代码 helper。

### B. wjh 使用中发现的问题（整合自原附录 A.5）
- 阶段二给出题目含无关内容，中间完整代码展示不完整（左侧拼凑代码完整、中间展示有缺失但可正常运行出正确结果）。
- 代码页右侧 AI 助手回答会重复。
- 提交评测偏 C++ 向，对 C 语言评估不够准确。
- AI 响应较慢，且 prompt 导致回复略显臃肿。
- 阶段二「请求提示」无法定位学生具体卡在哪个问题：常从阶段一从头解释再提问，难以解决当前卡点。

### C. 未解决问题 / 疑问
- 演示库 `session[DEMO_SESSION_KEY]`「先写再 seed」的时序脆弱；若中途失败，残留 key 与不完整演示库的状态如何自愈？
- `user_type`/`usertype` 键不一致是否已有调用方依赖旧写法？改动范围需要核对全部读取点。
- AI 新旧两层路径（`LLMEvaluator` 初始化/选型 vs `SharedLLMClient` 委托）何时收敛、是否会造成 provider 配置漂移？
- 仓库文档与代码存在差异：`PROJECT_UNDERSTANDING.md` 部分机制描述过期（如 AgentLoop 配置）；AGENTS.md 描述旧架构（`models/CNN.py` + CodeBERT/TextCNN）与实际 main 不符。
- 评测页轮询 60 次上限与「评测队列不可用」提示是否会被真实慢评测误触发，需压力验证。

---

## 六、个人理解与设想

### A. wjh 的设想与建议（整合自原附录 A，标注为个人想法、非现状）
1. **回复过滤 Agent 化**：不物理屏蔽全部代码；由专门 agent 监测回复，屏蔽与答案直接相关的代码、保留知识点示例代码，同时检查回复正确性。
2. **「老师—我—学生」三元角色**：老师 agent 布置讲解任务 → 我给“学生 agent”讲解该知识点 → 学生 agent 多角度追问（错误/模糊/缺失处）→ 我答不上时转老师 agent 提问；期望双智能体共享数据流，用算法适配「老师—我—学生」三向数据流通。
3. **自适应选题**：把 AI 互动中生成的追问沉淀进题库，用深度学习/自适应算法按学生水平分配题目。
4. **情感与学习积极性评估**：纳入对 AI 助手的使用程度、复习环节与效果评估等指标，综合评价学习积极性。
5. 学习计划：逐步补技术栈与项目细节，向学长/组内已有实现看齐。

### B. 本文档作者（AI 阅读方）的独立理解
- **设计亮点**：演示库请求级动态绑定 + 线程级二次校验的隔离设计，与「后台任务异步评测」配合，是单体应用里少见的干净实践；三阶段 + 费曼双 Agent 的服务端权威工具与「仅 /server-verify 校验通过才写 stage_pass」的收口，保证了阶段完成状态可信。
- **风险根因**：绝大多数权限/一致性问题源于两处历史演进——①登录态从自管 session 键迁移到 Flask-Login 时未清理旧读取点（`user_type`/`usertype`、跨蓝图权限不统一）；②路由层早期以「演示/调试优先」写接口（未认证 batch 端点、debug_session），在角色约束完备前已扩散到生产语义。
- **收敛建议（不涉及改动）**：若后续要加固，优先按「统一权限读取函数 + 单一来源角色常量」收敛双会话读取点，再逐个收紧 GET 写操作与 CSRF 覆盖面；AI 侧可顺势完成 LLMEvaluator → SharedLLMClient 的对象层收敛，消除 provider 双轨配置。
- **对 PR 文档的评价**：wjh 记录的证据标注约定与附录 B「范围澄清」具备可复核性，值得作为本仓库个人理解类文档的统一范式沿用。

---

## 附录 C：查阅文件与验证命令索引

**主要查阅范围**（本次综合理解所依据）：
- 入口/配置：`app.py`、`config.py`、`models.py`、`forms.py`、`wsgi.py`、`run.py`、`database_maintenance.py`、`deploy.sh`、`update.sh`
- 路由：`routes/`（auth、main、assignments、thinking、classes、users、grades、api 共 8 蓝图）
- 服务/任务：`services/`（llm_client、ai_evaluator、api_keys、course_grading、teacher_analytics、teacher_ai_advisor、demo_database、demo_experience）、`tasks/`（submission_tasks、ability_analysis）
- 工具与 Agent：`utils/`（sandbox_runner、code_evaluator、llm_evaluator、thinking_ai、guidance_generator、code_advisor、ability_scorer、async_tasks、sse、auth、api 等）、`utils/agents/`
- 前端与测试：`templates/`（57 模板）、`static/js/`（21 文件，含 sse-client）、`tests/`
- 文档：`README.md`、`README.en.md`、`CHANGELOG.md`、`PROJECT_UNDERSTANDING.md`、`project-understanding_wjh.md`

**验证命令索引**（源自 wjh 附录 B，本会话未执行）：
```powershell
py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
python run.py                                        # 启动（开发配置，本地 SQLite 自动建表）
.\.venv\Scripts\python.exe -m pytest tests/test_sandbox_features.py -q        # 3 passed
.\.venv\Scripts\python.exe -m pytest tests/test_sandbox_output_limits.py -q    # 5 passed
```
