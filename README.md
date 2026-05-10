<div align="center">

# CodeSense 酷森思

**基于因果隔离沙箱与启发式大模型的智能编程教育实训平台**

[![Version](https://img.shields.io/badge/版本-0.5.0-4361ee?style=flat-square)](https://github.com/XiaoCow666/CodeSense)
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=flat-square&logo=flask)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479a1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## 项目简介

CodeSense 酷森思是专为高校编程实训设计的**智能化评测与教学管理平台**。我们致力于解决传统 OJ（Online Judge）“只断对错，不教逻辑”的痛点，通过 AI 语义分析与动态沙箱执行的双轨驱动，打造“练-评-管”闭环的深度学习体验。

平台核心定位为**“启发式编程导师”**：它不直接向学生提供现成代码，而是通过对程序运行细节的捕捉和代码语义的深度理解，以引导、提问、类比的方式帮助学生自主修复 Bug，构建底层编程思维。

---

## 核心技术支柱

### 1. 因果隔离沙箱 (Causal Sandbox)
*   **安全隔离执行**：基于多层子进程隔离与资源配额管理（编译 15s/运行 5s 强制熔断），确保代码评测环境的绝对安全。
*   **异常深度截获**：不仅判断对错，更能精准捕获堆栈异常、内存溢出、死循环等因果细节，为 AI 诊断提供原始数据支撑。
*   **多语言兼容**：工业级支持 C++、Python 等主流教学语言。

### 2. 启发式 AI 导师 (Heuristic AI Tutor)
*   **四层阶梯式引导**：从基础分析（语法）、问题诊断（边界）、思路启发（类比）到优化建议（重构），由浅入深层层递进。
*   **引导不投喂**：内置严苛的 Prompt 策略，拒绝输出完整代码，强制诱导学生进行“逻辑补全”。
*   **实时流式反馈**：基于 SSE（Server-Sent Events）技术，实现 AI 指导建议的即时流式输出。

### 3. 多维能力画像 (Maturity & Ability Modeling)
*   **五大核心维度评分**：算法能力 (Algorithm)、代码风格 (Style)、功能完整性 (Functionality)、执行效率 (Efficiency)、代码可读性 (Readability)。
*   **成熟度指标 (Maturity Score)**：结合提交频率、分数稳定性、平均基准及进步梯度，构建学生个人的 $\phi$ 值成长模型。
*   **知识点热力追踪**：全量覆盖 C 语言核心知识点，直观展现班级学情分布。

---

## 功能模块

### 🚀 学生端：沉浸式实训体验
*   **工业级 Web IDE**：集成 Monaco Editor，支持智能提示、代码对比与历史提交回溯。
*   **实时 AI 助手**：对话式编程指导，支持 Markdown 渲染的优美格式化输出。
*   **能力进化视图**：动态展示雷达图、成长曲线及瓶颈作业分析。

### 📊 教师端：精细化教学管理
*   **AI 辅助出题**：基于大模型的作业格式化工具，自动解析自然语言描述并生成结构化题目。
*   **学情大数据驾驶舱**：班级平均水平对比、学生个体成长潜力预测、高风险学生预警。
*   **精细化视图隔离**：重构的 RBAC 权限体系，确保教师端与学生端的角色体验深度解耦。

### 🧪 实验性教学模块 (Alpha)
*   **思维链 (CoT) 训练场**：通过“分析-策略-审计”三阶段工作流，训练学生解决复杂问题的思维链路。
*   **积木编程 (Parsons Problems)**：支持代码块拖拽排序，降低语法门槛，专注于逻辑构建。

---

## 系统架构

```mermaid
graph TD
    User((学生/教师)) -->|SSE/REST| Web[Flask Core Server]
    Web -->|Async Tasks| Queue[Task Engine]
    Queue -->|Capture| Sandbox[Causal Sandbox]
    Sandbox -->|Stack Traces| AI[Heuristic AI Logic]
    AI -->|Heuristic Prompt| LLM[GLM-4 / GPT-4]
    LLM -->|Stream Output| User
    Web -->|Persist| DB[(MySQL 8.0)]
```

---

## 快速启动

### 1. 环境克隆与安装
```bash
git clone https://github.com/XiaoCow666/CodeSense.git
cd CodeSense
python -m venv venv
source venv/bin/activate  # Windows使用 venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置部署
复制 `env.example` 为 `.env` 并配置以下核心项：
*   `DATABASE_URL`: 数据库连接字符串（支持 MySQL/SQLite）。
*   `ZHIPU_API_KEY` 或 `OPENAI_API_KEY`: 大模型接口密钥。
*   `LOAD_LOCAL_MODEL`: 云端内存受限时建议设为 `False`。

### 3. 初始化与运行
```bash
# 初始化数据库
python -c "from models import db, app; app.app_context().push(); db.create_all()"
# 启动开发服务器
python app.py
```

---

## 更新日志

### [v0.5.0] - 2026-05 - 智能化全链路闭环
- **[重大升级]** 引入**成熟度模型 (Maturity Score)**，全面覆盖进步梯度与稳定性分析。
- **[体验优化]** 重构 RBAC 体系，实现学生、教师、管理员角色的**深度视图隔离**。
- **[功能上新]** 上线 **AI 辅助作业生成工具**，提升教师出题效率 70% 以上。
- **[实验性]** 发布 **“思维链 (CoT) 训练”** 原型，探索深度逻辑培养路径。
- **[架构优化]** 深度优化 SSE 流式响应，彻底解决云端部署下的重定向循环与性能抖动。

---

## 许可证
本项目基于 [MIT License](LICENSE) 协议。

如有疑问请访问 [saucodesense.com](http://saucodesense.com) 或提交 Issue。
opy env.example .env  # Windows
# 或
cp env.example .env  # Linux/Mac

# 编辑 .env 配置
notepad .env  # Windows
# 或
nano .env  # Linux/Mac
```

**关键配置项**：

```bash
# 数据库（开发环境可使用 SQLite）
DATABASE_URL='mysql+pymysql://user:password@127.0.0.1:3306/codesense'
# 或开发环境
DATABASE_URL='sqlite:///codesense.db'

# 应用密钥（生产环境至少 32 字符）
SECRET_KEY='your_secret_key_here_change_in_production'

# AI API（至少配置一个）
ZHIPU_API_KEY='your_zhipu_api_key_here'
OPENAI_API_KEY='your_openai_api_key_here'

# 安全配置（本地开发设为 false）
SECURE_COOKIES='false'

# 本地模型（云端 2G 内存建议设为 False）
LOAD_LOCAL_MODEL='False'
```

### 3. 安装沙箱依赖 (Linux/ECS)

```bash
sudo apt update && sudo apt install g++ -y
```

### 4. 初始化数据库

```bash
python -c "from models import db, app; app.app_context().push(); db.create_all(); print('Database initialized!')"
```

### 5. 运行

```bash
# 开发环境
python app.py

# 生产环境（使用 gunicorn）
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

---

## API 接口

### 核心接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/submit` | POST | 提交代码进行评测 |
| `/api/code_advice` | POST | 获取代码建议（聊天式） |
| `/api/get_programming_guidance` | POST | 获取编程指导 |
| `/api/ask_question` | POST | 学生提问 |
| `/api/format-assignment` | POST | AI 辅助作业格式化 |
| `/api/stream/ability-analysis` | GET | 流式能力分析 |

### 管理接口

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/users` | GET | 管理员 | 用户列表 |
| `/api/admin/batch-update-trends` | POST | 管理员 | 批量更新能力趋势 |
| `/api/admin/trend-statistics` | GET | 管理员 | 趋势统计 |

---

## 安全特性

- **沙箱隔离**：编译运行在受限环境中，防止恶意代码
- **Session 安全**：HttpOnly Cookie、SameSite 防 CSRF
- **教师邀请制**：24 小时过期 Token，防止未授权注册
- **权限分级**：学生/教师/管理员三权分立
- **提示词防注入**：识别并拒绝"角色扮演"等绕过尝试

---

## 云端部署

CodeSense 针对云端环境做了深度优化：

- **低内存运行**：跳过本地模型加载，2G 内存即可运行
- **环境变量配置**：代码与配置彻底分离
- **WSGI 生产级部署**：支持 gunicorn/uwsgi
- **HTTP Session 支持**：解决云服务器重定向循环问题

---

## 更新日志

### [v0.4.0] - 2026-03 - 工业级重构

- **[重大革新]** 上线"因果隔离沙箱"，支持真实用例执行与异常截获
- **[重大革新]** 引入"启发式引导提示词"，AI 从"工具人"升级为"导师"
- **[优化]** 实现异步评测系统，前端新增实时进度条显示
- **[安全]** 实现代码与配置彻底分离，支持 `.env` 敏感信息隐藏
- **[优化]** 支持多 AI 服务商切换（智谱/ OpenAI）
- **[优化]** 前端 Monaco Editor 集成，工业级代码编辑体验
- **[修复]** 解决云服务器 HTTP 环境下的登录重定向循环问题
- **[移除]** 舍弃了旧版的 TextCNN 评分模型，全面拥抱可解释的语义评估

---

## 许可证

本项目采用 [MIT License](LICENSE)。

感谢沈阳航空航天大学网络工程专业的试点支持。
如有任何问题，欢迎提交 Issue 或访问 [saucodesense.com](http://saucodesense.com)。

---

<div align="center">

**Made with ❤️ for better programming education**

</div>
