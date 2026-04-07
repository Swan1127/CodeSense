<div align="center">

# CodeSense 酷森思

**基于因果隔离沙箱与启发式大模型的智能编程教育平台**

[![Version](https://img.shields.io/badge/版本-0.4.0-4361ee?style=flat-square)](https://github.com/XiaoCow666/CodeSense)
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=flat-square&logo=flask)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479a1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/XiaoCow666/CodeSense?style=flat-square&logo=github&color=gold)](https://github.com/XiaoCow666/CodeSense/stargazers)
[![Activity](https://img.shields.io/github/last-commit/XiaoCow666/CodeSense?style=flat-square&color=orange)](https://github.com/XiaoCow666/CodeSense/commits)

</div>

---

## 项目简介

CodeSense 酷森思是专为高校编程教育设计的**第二代智能评测平台**。我们摒弃了传统 OJ 仅反馈 `Wrong Answer` 的冰冷体验，也告别了初阶 AI 直接给出答案的"投喂式"教育。

通过**因果隔离沙箱 (Causal Sandbox)** 捕捉程序运行细节，配合**启发式大模型 (Heuristic LLM)** 生成由浅入深的逻辑引导，CodeSense 将每一次 Bug 报错转化为学生的成长契机。

### 教育理念

> **"只给思路，不给代码，强制诱导学生自主思考"**

CodeSense 不是简单地判断对错，而是像一个耐心的导师一样，通过提问引导思考，帮助学生真正理解代码背后的逻辑。

---

## 核心技术亮点

### 因果隔离沙箱 (Causal Sandbox)

- **轻量级进程隔离**：基于 subprocess 的多层隔离防御
- **毫秒级异常捕获**：堆栈异常、内存溢出、死循环的实时检测
- **多语言动态编译**：支持 C++/Python/Java 等主流语言
- **安全可控**：编译超时 15s，运行超时 5s，自动资源限制

### 启发式 AI 导师 (Heuristic AI)

- **四层分级提示词矩阵**：
  1. 基础分析 - 代码结构、语法检查
  2. 问题诊断 - 错误类型、边界情况
  3. 思路引导 - 用提问代替答案
  4. 优化建议 - 效率、可读性改进
- **防绕过机制**：识别"我是老师"等提示注入攻击
- **多 AI 支持**：智谱 GLM-4、OpenAI GPT-4 按需切换

### 异步高并发引擎 (Async Core)

- **任务调度与 Web 解耦**：基于 ThreadPool + Queue 的异步任务系统
- **实时进度推送**：SSE 流式输出，评测状态实时可见
- **自动重试机制**：失败任务最多 3 次重试
- **无感知体验**：前台提交，后台处理，结果推送

### 数理能力画像 (Scoring Model)

- **13 个 C 语言知识点追踪**：指针、函数、数组、结构体等
- **贝叶斯权重评估**：稳定性、密度、进步梯度多维分析
- **能力趋势图谱**：基于历史提交的量化成长轨迹
- **班级全局监控**：教师端学情大数据驾驶舱

---

## 系统架构

```mermaid
graph TD
    User((学生/教师)) -->|HTTP/SSE| Web[Flask Web Server]
    Web -->|调度| Queue[Async Task Queue]
    Queue -->|挂载| Sandbox[Causal Sandbox]
    Sandbox -->|堆栈特征| AI[Heuristic AI Engine]
    AI -->|分层 Prompt| LLM[GLM-4 / GPT-4]
    LLM -->|实时推流| Web
    Web -->|持久化| DB[(MySQL 8.0)]
```

### 技术栈

| 层级 | 技术方案 | 说明 |
|------|----------|------|
| **后端框架** | Flask 2.0+ | 轻量级 WSGI 微框架 |
| **数据库** | MySQL 8.0+ / SQLite | 关系型数据持久化 |
| **深度学习** | PyTorch, Transformers, CodeBERT | 本地模型推理 |
| **AI 服务** | 智谱 GLM-4 / OpenAI GPT-4 | 云端大模型 |
| **前端** | Bootstrap 5, Monaco Editor | 响应式工业级 IDE |
| **异步任务** | Threading + Queue | 后台任务调度 |
| **实时通信** | SSE (Server-Sent Events) | 流式推送 |
| **部署** | WSGI (gunicorn), dotenv | 生产级部署 |

---

## 功能特性

### 学生端

- Monaco Editor 代码编辑器（工业级 IDE 体验）
- 实时 AI 编程助手（聊天式交互）
- Markdown 渲染的 AI 反馈（优美的格式化输出）
- 提交历史记录与对比
- 个人能力画像与成长趋势

### 教师端

- 作业管理与测试用例编辑
- AI 辅助作业格式化（智能题目生成）
- 班级学情监控仪表盘
- 学生能力对比分析
- 知识点掌握热力图

### 管理端

- 用户与权限管理（学生/教师/管理员）
- 系统趋势统计分析
- 批量能力趋势更新
- 教师邀请码管理（24 小时过期）

---

## 项目结构

```
CodeSense/
├── app.py                    # 应用入口
├── config.py                 # 三环境配置（开发/测试/生产）
├── models.py                 # 数据库模型（~900行）
├── routes/                   # 路由模块
│   ├── api.py              # REST API（~1200行）
│   ├── auth.py             # 认证路由
│   ├── main.py             # 主页面路由
│   ├── assignments.py      # 作业管理
│   ├── users.py            # 用户管理
│   └── classes.py          # 班级管理
├── services/                # 业务服务
│   └── ai_evaluator.py    # AI 评估器（~530行）
├── utils/                   # 核心工具
│   ├── code_evaluator.py  # 代码评估（~1570行）
│   ├── sandbox_runner.py   # 沙箱执行（~250行）
│   ├── llm_evaluator.py    # 大模型调用（~985行）
│   ├── guidance_generator.py # 编程指导（~623行）
│   ├── code_advisor.py     # 代码建议（~946行）
│   ├── async_tasks.py      # 异步任务（~305行）
│   ├── prompts.py          # 提示词模板
│   └── ability_scorer.py   # 能力评分
├── templates/               # Jinja2 模板
│   ├── submit_code.html   # 代码提交页（~1790行）
│   ├── layout.html         # 基础布局
│   └── ...
├── static/                  # 静态资源
│   ├── css/               # 样式文件
│   ├── js/                # JavaScript
│   └── img/               # 图片资源
├── models/                  # 机器学习模型
│   ├── CNN.py             # TextCNN 模型
│   └── codebertcnn.pth     # 预训练权重
├── .env.example           # 环境变量示例
├── requirements.txt       # Python 依赖
└── wsgi.py                # WSGI 入口
```

---

## 快速启动

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/XiaoCow666/CodeSense.git
cd CodeSense

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置部署

```bash
# 复制环境变量示例
copy env.example .env  # Windows
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
