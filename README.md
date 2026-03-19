<div align="center">

# CodeSense 酷森思

**基于深度学习与大语言模型的智能代码评估平台**

[![Version](https://img.shields.io/badge/版本-0.3.0-4361ee?style=flat-square)](https://github.com/XiaoCow666/CodeSense)
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=flat-square&logo=flask)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-4479a1?style=flat-square&logo=mysql&logoColor=white)](https://mysql.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/XiaoCow666/CodeSense?style=flat-square&logo=github)](https://github.com/XiaoCow666/CodeSense/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/XiaoCow666/CodeSense?style=flat-square)](https://github.com/XiaoCow666/CodeSense/commits)
[![Issues](https://img.shields.io/github/issues/XiaoCow666/CodeSense?style=flat-square)](https://github.com/XiaoCow666/CodeSense/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square)](https://github.com/XiaoCow666/CodeSense/pulls)

</div>

---

## 项目简介

CodeSense 酷森思是面向高校编程课程的**智能代码评估平台**，支持学生、教师、管理员三种角色。系统采用 **TextCNN + 启发式规则 + 智谱 GLM-4-Flash** 混合评分机制，对学生代码进行多维度自动评估，并通过 SSE 实时流式推送结果，同时提供 RAG 增强的 AI 编程助手与个性化学情分析。

**核心亮点**

- 双引擎混合评分：TextCNN x GLM-4-Flash，准确且可解释
- SSE 实时流式反馈：评估结果逐字推送，秒级响应
- RAG 个性化 AI 助手：关联历史错误与能力画像
- 完整三角色 RBAC：学生 / 教师 / 管理员严格权限隔离
- 作业截止日期全链路：设置、展示、标识一体化
- 安全邀请机制：教师注册链接 24h 过期 + 单次使用

---

## 系统截图

> 将截图放于 `docs/screenshots/` 目录后图片将在此显示。

| 学生首页 | 代码提交与评估 |
|----------|----------------|
| ![学生首页](docs/screenshots/student_home.png) | ![代码提交](docs/screenshots/submit_code.png) |

| 编程能力分析 | AI 编程助手 |
|--------------|-------------|
| ![能力分析](docs/screenshots/ability_analysis.png) | ![AI助手](docs/screenshots/ai_assistant.png) |

| 教师班级管理 | 管理员仪表盘 |
|--------------|---------------|
| ![班级管理](docs/screenshots/class_management.png) | ![仪表盘](docs/screenshots/admin_dashboard.png) |

---

## 主要功能

### 学生端

| 功能 | 描述 |
|------|------|
| 在线代码编辑与提交 | Monaco Editor，支持 C++ / Python / Java |
| 多维度自动评分 | CNN + 启发式 + GLM-4-Flash 混合评分，SSE 实时输出 |
| 编程能力分析 | 知识点掌握度、得分趋势、提交统计图表 |
| AI 个性化学情报告 | 新提交后异步更新，Markdown 渲染展示 |
| AI 编程助手（RAG） | 关联个人学情与历史错误，个性化回答 |
| 选中代码快捷提问 | 编辑器选中内容自动注入 AI 上下文 |
| 近期作业展示 | 含截止日期、Markdown 渲染、提交状态标识 |

### 教师端

| 功能 | 描述 |
|------|------|
| 班级管理 | 查看所负责班级、学生名单、整体学情 |
| 班级横向对比 | 多班平均分、提交量、知识点掌握度对比 |
| 学生详情查看 | 提交记录、得分趋势、AI 评估建议 |
| 作业发布 | 支持截止日期、Markdown 描述、知识点标注 |

### 管理员端

| 功能 | 描述 |
|------|------|
| 用户管理 | 分角色详情页，支持搜索、筛选、删除 |
| 教师邀请注册 | 24h 有效、单次使用的安全 Token 链接 |
| 系统仪表盘 | 用户角色分布、活跃度趋势、系统日志 |
| 数据导出 | 系统数据批量导出 |

---

## 技术架构

```
┌──────────────────────────────────────────────────┐
│                    前端层                         │
│  Bootstrap 5 · Chart.js · Monaco Editor         │
│  marked.js · DOMPurify · SSE 流式接收            │
└─────────────────┬────────────────────────────────┘
                  │ HTTP / SSE
┌─────────────────▼────────────────────────────────┐
│                  Flask 应用层                     │
│  routes/ · utils/ · models.py · forms.py        │
│  Flask-Login · SQLAlchemy · itsdangerous         │
└────────┬─────────────────────┬───────────────────┘
         │                     │
┌────────▼────────┐  ┌─────────▼──────────────────┐
│   MySQL 数据库   │  │       AI 评估引擎            │
│  users          │  │  TextCNN (PyTorch)          │
│  assignments    │  │  启发式规则评分              │
│  submissions    │  │  智谱 GLM-4-Flash API       │
│  invite_tokens  │  │  RAG 个性化上下文            │
│  system_logs    │  └────────────────────────────┘
└─────────────────┘
` + "``"
```

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | Flask 2.0+ | 蓝图模块化，轻量可扩展 |
| ORM | SQLAlchemy | 模型定义 + 启动自动迁移 |
| 认证 | Flask-Login + itsdangerous | 会话管理 + 安全 Token |
| AI 评估 | PyTorch TextCNN | 代码结构质量评分 |
| 大模型 | 智谱 GLM-4-Flash | 语义理解与自然语言反馈 |
| 流式输出 | Server-Sent Events | 实时评估结果推送 |
| Markdown | marked.js + DOMPurify | 安全渲染富文本内容 |
| 代码编辑器 | Monaco Editor | VS Code 同款编辑器 |

---

## 快速启动

### 系统要求

- Python 3.8+
- MySQL 8.0+
- 4GB+ RAM（推荐 8GB）

### 1. 克隆仓库

```bash
git clone https://github.com/XiaoCow666/CodeSense.git
cd CodeSense
```

### 2. 创建虚拟环境

```bash
# conda（推荐）
conda create -n student-eval python=3.8
conda activate student-eval

# 或 venv
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/Mac
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp env.example .env
```

编辑 `.env`：

```ini
SECRET_KEY=your_secret_key
DATABASE_URL=mysql+pymysql://user:password@localhost/student_code_review
ZHIPU_API_KEY=your_zhipu_api_key
```

> 智谱 API Key 申请：https://open.bigmodel.cn/

### 5. 启动

```bash
python app.py
```

首次启动自动建表并执行字段迁移，访问 http://localhost:5000

### 6. 导入示例作业（可选）

```bash
python scripts/add_assignments.py
```

导入 20 道算法题目（排序、数据结构、动态规划、图算法等）。


---

## 快速启动

### 系统要求

- Python 3.8+
- MySQL 8.0+
- 4GB+ RAM（推荐 8GB）

### 1. 克隆仓库

    git clone https://github.com/XiaoCow666/CodeSense.git
    cd CodeSense

### 2. 创建虚拟环境

    # conda（推荐）
    conda create -n student-eval python=3.8
    conda activate student-eval

### 3. 安装依赖

    pip install -r requirements.txt

### 4. 配置环境变量

    cp env.example .env

编辑 .env：

    SECRET_KEY=your_secret_key
    DATABASE_URL=mysql+pymysql://user:password@localhost/student_code_review
    ZHIPU_API_KEY=your_zhipu_api_key

智谱 API Key 申请：https://open.bigmodel.cn/

### 5. 启动

    python app.py

首次启动自动建表并执行字段迁移，访问 http://localhost:5000

### 6. 导入示例作业（可选）

    python scripts/add_assignments.py

导入 20 道算法题目（排序、数据结构、动态规划、图算法等）。

---

## 项目结构

    CodeSense/
    ├── app.py                    # 唯一启动入口
    ├── config.py                 # 环境配置
    ├── models.py                 # 数据库模型（含自动迁移）
    ├── forms.py                  # 表单定义
    ├── requirements.txt          # 依赖清单
    ├── env.example               # 环境变量模板
    ├── routes/                   # 路由蓝图
    │   ├── api.py                #   AI评估/SSE/代码助手
    │   ├── assignments.py        #   作业管理
    │   ├── auth.py               #   认证/邀请教师
    │   ├── classes.py            #   班级管理
    │   ├── main.py               #   首页/仪表盘
    │   └── users.py              #   用户管理
    ├── utils/                    # 工具模块
    │   ├── code_evaluator.py     #   CNN+启发式评分
    │   ├── llm_evaluator.py      #   GLM-4-Flash评估
    │   ├── guidance_generator.py #   个性化建议生成
    │   ├── code_advisor.py       #   AI编程助手（RAG）
    │   └── auth.py               #   权限装饰器
    ├── templates/                # Jinja2模板
    ├── static/                   # 静态资源
    ├── scripts/                  # 运维脚本
    └── tasks/                    # 后台异步任务

---

## 角色与权限

| 功能 | 学生 | 教师 | 管理员 |
|------|:----:|:----:|:------:|
| 提交代码/查看评分 | ✓ | | |
| 编程能力分析 | ✓ | | |
| AI编程助手 | ✓ | | |
| 班级管理/学情查看 | | ✓ | ✓ |
| 作业发布/管理 | | ✓ | ✓ |
| 用户管理 | | | ✓ |
| 邀请教师注册 | | | ✓ |
| 系统仪表盘 | | | ✓ |

默认账户：用户名 admin / 密码 admin123
教师账户由管理员通过「邀请教师」功能生成一次性链接创建。

---

## 更新日志

### v0.3.0 (2026-03-19)
- 新增作业截止日期字段（模型/表单/模板全链路）
- 新增教师邀请 Token 单次使用 + 24h 过期（InviteToken 模型）
- 新增管理员/教师用户详情分角色页面
- 管理员仪表盘用户类型分布图新增教师角色统计
- 全站 Markdown 渲染覆盖（学生首页近期作业、作业详情等）
- 修复教师视图越权按钮（编辑班级、返回用户管理）
- 修复教师「返回个人中心」路由错误
- 修复作业详情页教师视图显示「开始作答」问题
- 清理冗余迁移脚本、测试模板、历史 py 文件

### v0.2.0
- 集成智谱 GLM-4-Flash 流式评估
- 班级对比分析功能
- AI 个性化学情分析
- SSE 实时反馈

### v0.1.0
- 初始版本：用户管理、作业管理、代码提交与 CNN 评估

---

## 许可证

MIT License © 沈阳航空航天大学

联系邮箱：daiyupeng5@gmail.com
