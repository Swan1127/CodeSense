# 学生程序设计能力评价系统
# Student Code Evaluation System

![版本](https://img.shields.io/badge/版本-0.2.0-blue.svg)
![许可证](https://img.shields.io/badge/许可证-MIT-green.svg)
![Python版本](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)
![Flask版本](https://img.shields.io/badge/Flask-2.0%2B-red.svg)

基于深度学习的代码智能评估平台，为教育机构提供自动化的学生代码评估解决方案。

## 项目概述

学生程序设计能力评价系统是一个基于人工智能的代码评估平台，旨在解决传统编程教学中存在的问题，包括评价主观性强、反馈不及时、教师工作量大等。系统利用人工智能技术对学生提交的代码进行自动评估，从算法能力、代码风格、功能实现和效率优化等多个维度给出评分和改进建议，提供即时反馈，帮助学生提高编程能力。

## 最新更新 (2023-04-09)

- 优化了代码评估算法
- 修复了用户界面的若干问题
- 提升了系统整体性能
- 更新了依赖库版本

## 主要功能

- **用户管理**：学生账户与管理员账户的管理
- **作业管理**：发布、修改、查看作业
- **代码提交**：在线编辑、提交代码
- **代码评估**：自动评估代码质量，多维度打分，提供反馈
- **大模型评估**：集成大型语言模型进行智能代码分析
- **数据分析**：学习情况分析、统计图表
- **系统管理**：系统日志、数据导出、系统设置

## 技术栈

### 前端技术
- HTML5/CSS3/JavaScript
- Bootstrap 5
- Chart.js
- CodeMirror
- jQuery

### 后端技术
- Python 3.8+
- Flask 2.0+
- SQLAlchemy
- Flask-Login
- Flask-WTF
- SQLite/MySQL

### AI技术
- PyTorch
- 深度学习模型支持
- TextCNN
- 大型语言模型API (智谱GLM-4/OpenAI API)

## 系统截图

![登录界面](screenshots/login.png)
![管理员仪表盘](screenshots/admin_dashboard.png)
![代码提交](screenshots/code_submission.png)
![评估结果](screenshots/evaluation_result.png)

## 安装指南

> **⚠️ 重要提示：** 本项目已全面升级安全配置，所有敏感信息通过环境变量管理。  
> 详细的安全配置和部署指南请参考：
> - 📖 [部署指南 (DEPLOYMENT.md)](DEPLOYMENT.md)
> - 🔒 [安全配置指南 (SECURITY.md)](SECURITY.md)

### 系统要求

- Python 3.8或更高版本
- pip包管理器
- 虚拟环境工具（推荐使用venv或conda）
- 至少4GB RAM（推荐8GB或更多，特别是运行AI模型时）
- 至少2GB可用磁盘空间

### 快速开始（开发环境）

#### 1. 配置环境变量

```bash
# 复制环境变量模板
cp env.example .env

# 生成安全密钥
python -c "import secrets; print(secrets.token_hex(32))"

# 编辑.env文件，填入生成的密钥和其他配置
# 开发环境可以不设置DATABASE_URL（将使用SQLite）
```

#### 2. 运行安全检查

```bash
# 验证配置是否正确
python scripts/security_check.py
```

### 安装步骤

1. **获取源代码**

```bash
# 克隆代码仓库
git clone https://github.com/yourusername/Student-Code-Evaluation-System.git
cd Student-Code-Evaluation-System
```

2. **创建并激活虚拟环境**

```bash
# 使用venv创建虚拟环境
python -m venv venv

# Windows下激活虚拟环境
venv\Scripts\activate

# Linux/Mac下激活虚拟环境
source venv/bin/activate
```

3. **安装依赖包**

```bash
# 安装项目依赖
pip install -r requirements.txt
```

4. **初始化数据库**

```bash
# 初始化数据库
flask db init
flask db migrate -m "Initial migration"
flask db upgrade

# 创建测试数据（可选）
python init_db.py
```

5. **下载AI模型文件**

```bash
# 下载预训练模型文件
python download_models.py
```

6. **配置AI API密钥**

在 `.env` 文件中添加API密钥：
```bash
# 智谱AI API密钥（推荐）
ZHIPU_API_KEY=your_zhipu_api_key

# 或使用OpenAI API密钥
# OPENAI_API_KEY=your_openai_api_key
```

获取API密钥：
- 智谱AI: https://open.bigmodel.cn/
- OpenAI: https://platform.openai.com/

7. **启动应用**

```bash
# 开发环境运行
flask run

# 或者使用Python直接运行
python run.py
```

应用将在默认端口5000上运行，访问http://localhost:5000即可打开系统。

8. **数据库迁移** (升级时)

如果您是从旧版本升级，请运行迁移脚本添加新字段:
```bash
python migrations/add_ai_feedback.py
```

## 使用指南

### 管理员账户

- 默认用户名：`admin`
- 默认密码：`admin123`

登录后可以管理用户、发布作业、查看统计信息、导出数据、配置系统设置等。

### 学生账户

新用户可通过注册页面创建学生账户。学生可以:
- 查看作业列表
- 提交代码
- 获取自动评估结果和大模型智能分析
- 查看个人学习统计

## 大模型评估功能 (新增)

系统现在支持使用大型语言模型(LLM)对学生代码进行更全面的评估和反馈:

- **智能代码评析**: 基于先进的语言模型分析代码结构、逻辑和实现
- **详细质量反馈**: 提供更详细、更有针对性的代码质量反馈
- **改进建议**: 智能生成代码改进建议和优化方向
- **自然语言解释**: 以易于理解的自然语言解释评分结果

要使用此功能，您需要:
1. 在.env文件中配置API密钥
2. 系统将自动检测并启用大模型评估功能
3. 学生提交代码后可在评估结果页面查看大模型反馈

## 项目结构

```
Student-Code-Evaluation-System/
├── app.py              # 应用入口
├── config.py           # 配置文件
├── models/             # 数据模型
├── routes/             # 路由控制
├── services/           # 业务逻辑
├── static/             # 静态资源
├── templates/          # HTML模板
├── utils/              # 工具函数
│   ├── code_evaluator.py  # 代码评估逻辑
│   └── llm_evaluator.py   # 大模型评估模块(新增)
├── models/             # 模型相关文件（训练权重等）
├── tests/              # 测试代码
├── migrations/         # 数据库迁移文件
├── requirements.txt    # 依赖包列表
└── README.md           # 项目说明
```

## 功能亮点

- **多维度代码评估**：不仅关注代码的功能正确性，还评估算法设计、代码风格和效率优化
- **大模型智能分析**：利用先进的大型语言模型提供人性化的代码评价和建议
- **即时反馈**：学生提交代码后立即获得评估结果和改进建议
- **个性化学习分析**：基于历史提交数据，生成个性化的学习进度和能力分析
- **直观的数据可视化**：使用各类图表直观展示学习情况和系统运行数据
- **完善的用户管理**：支持搜索、筛选和管理用户
- **灵活的作业管理**：支持作业的创建、编辑、删除和排序
- **数据导出功能**：支持导出系统数据用于备份或进一步分析

## 贡献者

- 开发者1：负责前端开发与UI设计
- 开发者2：负责后端开发与数据库设计
- 开发者3：负责AI模型开发与集成
- 开发者4：负责测试与文档编写

## 许可证

本项目采用MIT许可证。详见 [LICENSE](LICENSE) 文件。

## 联系方式

如有问题或建议，请联系：
- 邮箱：support@codeeval.example.com
- 项目Github：https://github.com/yourusername/Student-Code-Evaluation-System

## 更新日志

### v0.1.2 (2024-06-20)
- 集成大型语言模型进行智能代码评估
- 添加详细代码反馈和改进建议功能
- 改进数据库架构，添加新的评估字段
- 优化提交处理逻辑，提高系统稳定性
- 更新用户界面，支持更详细的评估结果展示
- 完善API功能，支持更多参数选项

### v0.1.1 (2024-06-01)
- 修复了用户管理页面的搜索功能
- 添加了作业管理页面的排序功能
- 实现了系统活动日志功能
- 用真实数据替换了示例数据
- 优化了系统统计图表性能
- 改进了管理员仪表盘界面

### v0.1.0 (2024-05-15)
- 初始版本发布
- 实现基本用户管理功能
- 实现基本作业管理功能
- 实现代码提交和评估功能
- 支持多种评估模式（大模型API + 传统算法）
- 实现基础数据统计功能 