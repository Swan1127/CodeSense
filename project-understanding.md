一、
项目定位
CodeSense是一个面向高校编程教学的AI辅助评测与学习平台 。它把代码提交、受限执行、AI辅导、分阶段练习、学情分析放进同一条学习链路。核心定位是：引导学生自己学会，而不是替学生写出答案。

主要用户
1.学生：提交C++程序、查看测试结果和反馈，进入三阶段引导式学习流程，记录自己的思路与解释。
2.教师：创建和管理作业、组织班级与花名册，查看提交记录、作业完成情况、知识点和能力趋势。
3.开发者/研究者：在Flask、SQLAlchemy和可替换的AI服务接口上继续扩展评测、教学和数据分析能力。

核心问题
传统OJ的两个痛点正是这个项目要解决的核心问题：
1. 对学生：只看到"对/错"，不知道问题出在哪。传统评测只给二元结果，学生无法定位问题究竟在思路、实现、边界条件还是调试过程。CodeSense引入受限评测（Causal Sandbox）+ AI辅导，并把一次练习拆成三阶段，强制学生先讲思路、再组装步骤、最后用自己的话解释（费曼教学），让"理解"过程可见、可评估。
2. 对教师：反馈零散、共性问题难发现。教师要在大量提交记录里人工找共性问题，再把零散反馈整理成教学安排，成本高。CodeSense用能力画像（算法、代码风格、功能完整性、执行效率、可读性等维度）和知识点趋势，把学生表现沉淀为可统计、可下钻的学情数据，辅助教师定位需要补练的内容。

二、
顶层文件（入口与配置）
run.py：开发启动入口，默认走开发配置
app.py：应用工厂
create_app() ：注册Blueprint、初始化DB/会话/登录态、ProxyFix、后台任务、访问日志与压缩中间件
wsgi.py；生产WSGI入口（默认生产配置），配合gunicorn_config.py config.py development / testing / production三套配置，读取.env
models.py：全部ORM模型（见下）
forms.py：Flask-WTF表单定义
database_maintenance.py：生产一次性建表/迁移/索引维护
deploy.sh / update.sh / gunicorn_config.py：部署与运维脚本、Gunicorn配置
routes/ — Web与API路由层（Blueprint）
auth.py：登录/登出/注册/教师邀请，角色认证
main.py：首页、关于、帮助等基础页面
assignments.py：作业CRUD、测试用例与提交管理
thinking.py：三阶段引导式学习（思路/积木/费曼）与阶段Agent API
classes.py：班级、花名册、导入与班级统计
users.py：用户资料、学生/教师/管理员页面
grades.py：成绩视图与课程评分
api.py：提交评测、代码建议、能力分析SSE等REST接口
services/ — 面向业务的"较厚"服务层
llm_client.py：智谱/OpenAI多provider客户端、重试、限流与熔断
ai_evaluator.py：AI评测（含流式能力分析）
api_keys.py：API密钥管理器（不落库明文）
course_grading.py：课程成绩计算
teacher_analytics.py：教师端班级/知识点学情统计
teacher_ai_advisor.py：AI学情建议
demo_database.py / demo_experience.py：公开体验入口的临时SQLite会话隔离与演示数据
utils/ — 底层工具与核心引擎
sandbox_runner.py：Causal Sandbox：g++ C++17受限编译/运行、超时与输出限制
code_evaluator.py：本地ML评分（CodeBERT + TextCNN）
llm_evaluator.py：LLM代码评价
guidance_generator.py：启发式引导提示生成（不直接给答案）
code_advisor.py：代码建议
ability_scorer.py / maturity_calculator.py：贝叶斯能力画像与成熟度
async_tasks.py / sse.py：线程池任务队列+SSE流式推送
thinking_ai.py：三阶段引导AI交互
markdown_formatter.py：格式化输出
prompts.py：提示词模板agents/阶段三费曼/论坛Agent子系统： orchestrator编排、 loop多轮对话、memory、tools、intent/goal/coverage意图与覆盖判定、contracts契约
auth.py、api.py、validate_testcases.py：认证辅助、通用 API、测试用例校验
tasks/ — 异步任务
submission_tasks.py：提交后评测、AI 分析等后台任务；
ability_analysis.py：能力画像的异步计算与分析。

前端
- templates/ ：Jinja2页面。含按角色区分的首页/详情页，以及thinking/arena.html （三阶段竞技场）、组件化的多种代码编辑器片段。
- static/ ：CSS、JS（Monaco按需加载、SSE客户端、编辑器/提交/思路对话脚本、安全输出处理器）、图片与第三方库（Sortable、require.min.js）。
核心模型一览（models.py）
用户与组织：User（学生/教师/管理员）、Class、StudentRoster、InviteToken（教师邀请）；
教学资源： Assignment、 AssignmentKnowledgePoint、 TestCase、 AssignmentThinkingPreset（三阶段预设）；
学习记录：Submission、ThinkingSession、ThinkingStageLog、StudentQuestion、CodeAdviceRequest ；
画像与学情：AbilityTrend、KnowledgePointScore、TeacherAISuggestion；
平台支撑：SystemLog、SystemConfig、CodeSenseSession（会话持久化）。
测试（tests/）
覆盖面较广，突出三类特色域：沙箱评测（test_sandbox_features）、演示会话隔离（test_demo_*）、阶段三Agent/论坛（test_stage3_*），另有SSE、成绩、班级花名册、HTTPS代理与性能基线等测试。
三、核心运行流程、关键数据流或调用链
1. 应用启动与请求生命周期
run.py / wsgi.py → app.py 的 create_app() ：加载 config 、 db 、注册所有 Blueprint（ routes/ ）、接入 Flask-Login / Flask-Session、ProxyFix、后台任务队列与压缩/日志中间件。请求进入 Blueprint 路由，经 services/ 编排，落到 utils/ 引擎与数据库。

2. 代码提交 → 评测调用链（最重要的一条）
代码提交有两条平行通路：

A. 网页表单路径（异步，主流） POST /assignments/<assignment_id>/submit （ routes/assignments.py:483 ）→ 创建 Submission(status=pending) → 把任务投进后台线程 evaluate_submission_async() （ tasks/submission_tasks.py ）→ 页面跳转到"评测中"，由 get_submission_status / SSE 轮询进度。

后台线程按序执行（tasks/submission_tasks.py:66-279）：
1. AI 基础评估：evaluate_cpp_code()（ utils/code_evaluator.py:775 ），内部为启发式评分 calculate_heuristic_score + 可选的LLM反馈，产出 score/feedback ；
2. 沙箱用例评判 ： run_test_cases() （ utils/sandbox_runner.py:163 ）→ compile_cpp() 用 g++ 按 C++17 编译（15s 超时）→ run_single_test() 逐用例运行（5s 超时、输出长度限制）→ 写回 sandbox_passed/total/detail ；
3. 分数归一 ： _normalise_score 把各评测器（0–100/0–10/0–5）统一压到0–5 ；
4. 统计刷新 ： _refresh_assignment_stats / _refresh_user_stats 基于全量历史重算，避免种子数据重复累加；
5. 知识点画像 ：用作业绑定或 AI 探测出的知识点调 KnowledgePointScore.update_score ；
6. 触发能力分析 ： AbilityTrend.mark_as_outdated + trigger_analysis_if_needed() ；
7. 状态置为 evaluated ，写 SystemLog 。
B. API 路径（同步） POST /api/submit （ routes/api.py:269 ）：同步 evaluate_cpp_code + 更新作业统计 + 触发能力分析，直接 JSON 返回 submission_id/score/status 。

数据落库： Submission （含 sandbox_* 、 ai_feedback ）→ Assignment / User 聚合 → KnowledgePointScore → AbilityTrend 。

3. 三阶段引导式学习调用链
入口 GET /thinking/<assignment_id> （ routes/thinking.py:859 ）加载 arena.html ：

1. 会话初始化 ： POST /api/start_session 创建 ThinkingSession ，装载 AssignmentThinkingPreset （目标、关键步骤、提示语）；无预设时走 AI 生成并 lazy 回填。
2. 阶段一（思路） ： /api/stage1/submit → evaluate_description() （ utils/thinking_ai.py ）先做本地快速检查、必要时请求 AI，按 key_steps 匹配打分；≥50 分放行至阶段二，逐条写 ThinkingStageLog 。
3. 阶段二（组装） ： /api/stage2/verify 验证步骤顺序并把组装结果规整成可编译代码，生成预览；AI 回应统一经 sanitize_response （ utils/thinking_ai.py ）做 物理级代码过滤 ——这是提示词约束之外的第二层防泄漏。
4. 阶段三（费曼/论坛） ： /api/stage3/forum/message → Stage3Orchestrator.handle_user_message （ utils/agents/orchestrator.py:50 ）→ 意图识别 intent 、目标角色仲裁（学生/教师双 Agent）、 loop 多轮、 tools 追问/探测、 coverage 判定掌握度，SSE 流式返回； /api/stage3/forum/trace 提供轨迹复盘， /api/complete_session 收尾归档。
5. 全部通过 AI 服务层 SharedLLMClient （ services/llm_client.py ），支持智谱/OpenAI 多 provider 重试、限流、熔断与单飞合并。
## 4. 能力画像与教师端学情链路
每次提交都会触发： AbilityTrend.mark_as_outdated → trigger_analysis_if_needed() （防并发 key 去重）→ 后台线程 generate_ability_analysis_async() （ tasks/ability_analysis.py ）→ 拉最近 20 条提交 → AIEvaluator.analyze_ability_trend_stream() （ services/ai_evaluator.py:342 ）→ 前端经 /api/stream/ability-analysis （SSE， routes/api.py:1195 ）流式渲染 Markdown → 结果落回 AbilityTrend 。教师端 teacher_analytics / teacher_ai_advisor 再从班级、知识点维度做聚合视图与建议。

AI 统一出口 ：所有 AI 请求最终经 services/llm_client.py 的 SharedLLMClient ，避免各调用方各自直连。
公开体验隔离 ： services/demo_database.py 为每次体验建临时 SQLite， demo_run_id 沿提交、沙箱、能力分析各后台线程传递；线程执行前二次校验会话存活，退出即清理，绝不写正式库。
失败可见性 ：AI/沙箱失败在体验中一律置 failed ，前端显示"失败/重试"，不允许用默认分数伪装成功。

四、CodeSense 安装、运行与测试记录
记录时间 ：2026-09-03 环境 ：Windows，Python 3.11（项目虚拟环境 .venv ），g++ 16.1.0（MSYS2） 项目 ： D:\MyCodesence\CodeSense （CodeSense v1.0.0）

一、安装
按 README「快速开始」在项目根目录完成：
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
依赖安装成功，共 60 个包，核心版本为 Flask 2.2.3、SQLAlchemy 2.0.52、python-docx 1.2.0、openai 3.7.0、cryptography 41.0.3 等。随后安装 C++ 编译器 g++ 16.1.0（MSYS2），路径 C:\msys64\mingw64\bin\g++.exe ，与项目 utils/sandbox_runner.py 的编译器候选路径一致。

过程中遇到的问题与解决 ：
1. Python 3.14 兼容性问题 ：系统 Python 为 3.14，Flask 依赖的 Werkzeug 2.2.3 使用已被 3.12+ 移除的 ast.Str ，启动即报 AttributeError: module 'ast' has no attribute 'Str' 。改用 Python 3.11 创建虚拟环境后解决。
2. .env 残留 MySQL 配置 ： .env 中的 DATABASE_URL 实际仍指向本地 MySQL（ user:password@127.0.0.1:3306 ），启动时 db.create_all() 连接 MySQL 被拒（WinError 10061）。注释该行后回退到本地 SQLite 数据库。
二、运行
开发配置启动（未设置 DATABASE_URL 时使用本地 SQLite，首次启动自动建表）：
.\.venv\Scripts\Activate.ps1
python run.py
启动结果：数据库初始化成功，异步任务系统初始化成功； Running on http://127.0.0.1:5000 。本机未安装 Redis，会话自动降级为文件系统存储（filesystem），不影响使用。浏览器访问 http://127.0.0.1:5000/login ，登录页提供免注册的学生体验与教师体验入口。

说明 ：启动日志中的"生产模式：启用 INFO 级别日志"字样由 .env 内 FLASK_DEBUG='False' 引起，实际运行配置为 development （日志显示 Debug mode: on ），不构成问题。

三、测试
安装 pytest 后运行沙箱相关测试：
python -m pytest tests/test_sandbox_features.py -q
结果： 3 passed, 26 warnings in 14.86s 。三项用例全部通过；26 条警告均为框架弃用提示（Flask 2.3 session_cookie_name 、SQLAlchemy Query.get() 等），不影响功能。全量测试集（ tests ）中的部分用例依赖真实 AI 服务密钥与 Redis，未配置时会失败，属预期行为，未纳入本次验证范围。

四、结论
本项目已在本地 Windows 环境完成安装、成功启动并通过沙箱评测相关测试，代码评测（C++ 编译执行）链路可正常使用；AI 辅助功能需在 .env 配置智谱或 OpenAI 密钥后启用。

五、风险疑问和后续需要确定的事项
1.当前题目中有些错误，如引导式学习的第二部分，给出的题目会多出一些无关内容，且中间完整代码展示处的代码也并不完整，看左侧题目做完后拼凑的代码是完整的，中间的有所缺失，但是能正常运行答出正确问题。
2.在代码页右侧的ai助手回答会重复
3.最后代码提交后的评估多是c++的，对c语言的评估不准确
4.当前codesence的ai响应有点慢，而且用的prompt缘故，回复有点太臃肿感觉，用起来有点卡手：（
5.第二阶段中的请求提示，无法直接确定到我做到哪个题出现了问题，他是根据前面第一阶段给的问题继续从头解释链表并提问的，这样无法直接帮助学生解决当前被卡住的问题，需要到这个问题处才能解释这个问题。我觉得可以把请求提示精确到问题上，直接给这个问题的提示，并提问与当前题目相关的问题辅助学生理解
6.后续的话我需要学习项目的相关技术栈，逐步了解相关知识。实践经验还是太少了，对项目相关内容好多我看不懂的，希望能逐步赶上学长进度吧

六、架构理解
CodeSense 是一个 Flask 单体 Web 应用（Python），核心是「C 语言/C++ 编程教学」：学生交代码 → 受限沙箱编译运行 → AI 启发式引导学习 → 沉淀能力画像；教师端管理班级/作业并查看学情。架构上采用「路由 → 服务 → 引擎/任务 → 模型」的分层，并配了一套会话级临时 SQLite 的公开演示隔离机制。

启动链路与配置
app.py 是唯一入口，create_app() 应用工厂：加载 config.py（development/testing/production 三套）→ 配置数据库连接池、Session（优先 Redis，失败降级文件系统）→ 初始化 db、Flask-Login、Flask-Session → 注册 8 个蓝图 → 初始化异步任务系统 → 自动建表。
run.py、wsgi.py、gunicorn_config.py 分别是本地开发、生产 WSGI、Gunicorn 启动配置。
根级还挂了全局 before_request：单点登录校验和demo 临时库激活（见下）。
目录分层
routes/ 蓝图/路由层（页面 + JSON/SSE API）：auth、main、assignments、users、classes、api、thinking（三阶段引导式学习）、grades（成绩导出）。只做参数解析、权限校验、编排服务，不写核心逻辑。
services/	业务服务层（较新、偏纯逻辑、易单测）：LLM 客户端抽象 llm_client.py、AI 评估 ai_evaluator.py、密钥管理 api_keys.py、成绩册 course_grading.py、教师分析 teacher_analytics.py、以及演示数据隔离 demo_database.py + demo_experience.py。
utils/ 引擎/工具层：代码评测 code_evaluator.py、沙箱执行 sandbox_runner.py、提示词 prompts.py、能力画像 ability_scorer.py、SSE 流 sse.py、权限装饰器 auth.py，以及三阶段 Agent 引擎 utils/agents/。
tasks/	后台任务：submission_tasks.py（异步评测）、ability_analysis.py。
models.py 单一 ORM 文件（~1500 行），约 20 个模型。
templates/ / static/	Jinja2 模板 + JS/CSS（含 Monaco 编辑器按需加载、SSE 客户端）。
tests/	pytest 测试，覆盖面很广（sandbox、SSE、demo 隔离、三阶段 agent/forum、成绩路由、性能基线等）。
关键数据模型（models.py）
角色与组织：User（usertype: 学生/教师/管理员 + RBAC）、Class、StudentRoster（班级花名册）。
作业与评测：Assignment、TestCase、Submission、AssignmentKnowledgePoint。
引导式学习：AssignmentThinkingPreset、ThinkingSession、ThinkingStageLog、StudentQuestion。
画像与分析：AbilityTrend、KnowledgePointScore、TeacherAISuggestion。
其它：InviteToken、SystemLog、SystemConfig。
核心子系统
1.代码评测执行链（Causal Sandbox）
这一段代码评测
以 g++ C++17 编译，15s 编译 / 5s 运行超时、临时工作目录、限输出长度、标准化输出比对。调用链大致是：
routes (submit) → tasks/submission_tasks.evaluate_submission_async
   → utils/code_evaluator（静态启发式 + 可选 AI 兜底）
   → utils/sandbox_runner.run_test_cases（受限编译运行）
注意：仓库已不再依赖本地 CodeBERT/TextCNN 模型（app.py 有明确日志说明），评测走启发式规则 + 已配置 AI 服务。

2. AI 服务抽象
llm_client.py 统一封装智谱/OpenAI，含 provider 健康状态、故障切换、退避重试；api_keys.py 统一管理密钥。上面的 guidance/advisor/评估都只依赖这一层。
    对ai助手的回复当前只在thinking_ai.py内做了直接屏蔽，我认为不应该完全屏蔽，可以做一个agent专门监测回复，把和答案直接相关的代码屏蔽掉，而有关知识点的例子代码保留，帮助学生理解，同时可以检查回复是否正确，提高回复的正确率。

3. 异步 + SSE
提交后不阻塞请求：任务由线程池执行，前端通过 utils/sse.py 的 SSE 流（如 /api/stream/ability-analysis）拿进度。

4. 三阶段引导式学习（thinking）
一次练习 = 思路描述 → 步骤组装 → 费曼教学（stage3）。费曼部分是一套较重的多角色 Agent 系统，全在 utils/agents/：
    第三阶段的问答中，我认为可以让老师agent给我一个任务让我给学生agent讲这个知识点，就是直接把我的理解全部讲完。然后让学生agent去提问。如果我给的知识点的大概描述有错误、模糊、缺失的地方，则直接让学生agent提问（即多角度检查）。如果我回答不上来，就可以转向老师agent提问。

feynman.py：双角色（教师/学生上下文）Agent 运行时；
    后面我觉得要让这两个智能体共享数据，数据流通模式是俩智能体共享知识，老师给我讲解和提问，我给学生讲解，学生给我提问缺陷处或者难懂处然后给出代码修复，从而构成三元关系，用算法适配
loop.py Agent 主循环、tools.py 工具、model.py 模型适配；
orchestrator.py 编排、intent.py 意图路由、memory.py 记忆、coverage.py 知识点覆盖评估、goal.py 目标管理、contracts.py 数据契约。
    自适应学生水平挑选问题的题目可以从咱们设定的ai助手处获取，ai助手给出的回答会生成问题辅助你思考，在此基础上优化题目进题库。然后通过深度学习自适应算法进行分配
入口路由在 thinking.py，页面在 arena.html。
5. 公开演示体验隔离（重点设计）
不注册真实账号也能体验：每次进入 /login 的体验入口会生成一个带随机 run_id 的独立临时 SQLite（demo_database.py），由 before_request 按会话激活该库；演示账号（demo:*）走 Flask-Login 的独立 user_loader。demo_experience.py 负责向临时库播种演示学生/作业/提交等数据，退出或超时（空闲 1h / 最长 2h）即删除。这就是 AGENTS.md 里 PR worktree 数据隔离约定与之一致的设计。

6. 成绩与画像
作业提交分 0–5 分；知识点/能力 0–100 分（贝叶斯权重，ability_scorer + AbilityTrend/KnowledgePointScore）。
    后续这个网站的情感分析功能（学习态度与积极性）我觉得可以纳入以下几个指标：对ai助手的使用程度评估；对作业开设一个习题复习处，设置复习环节，对复习效果进行评估。最后用算法综合评价该生的学习积极性。
grades.py + course_grading.py 汇总成绩册并导出 Excel；教师 AI 建议在 teacher_ai_advisor.py。
安全/运维要点
权限分三类装饰器：login_required / teacher_required / admin_required。
单点登录：before_request 比对 session 与库内 current_session_id，发现并发登录强制登出。
Session 优先 Redis，失败自动降级文件系统；生产强制 SECRET_KEY ≥32、DB_AUTO_INIT=False（需先跑 database_maintenance.py 建表/索引）。
提供 /healthz、/readyz 探针、ProxyFix 反代协议还原、gzip 压缩与慢请求日志。

使用的ai工具：trae接入ds-v4-flash
查阅的文件：
https://blog.csdn.net/byxdaz/article/details/147084976?ops_request_misc=elastic_search_misc&request_id=4c0d1eed18c742905a2f455a7e688b3e&biz_id=0&utm_medium=distribute.pc_search_result.none-task-blog-2~all~ElasticCommercialInsert~search_v2-1-147084976-null-null.142^v102^pc_search_result_base3&utm_term=msys2&spm=1018.2226.3001.4187

https://blog.csdn.net/qq_45712124/article/details/159283588?ops_request_misc=elastic_search_misc&request_id=7e7b8160aaef4b2fc94209e3c3a8befb&biz_id=0&utm_medium=distribute.pc_search_result.none-task-blog-2~all~top_positive~default-2-159283588-null-null.142^v102^pc_search_result_base3&utm_term=git%E5%91%BD%E4%BB%A4&spm=1018.2226.3001.4187