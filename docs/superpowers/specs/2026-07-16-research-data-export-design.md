# CodeSense 研究数据导出脚本设计

## 目标

提供一个可直接放到 CodeSense 线上部署目录运行的只读脚本，从平台现有数据库中提取论文研究所需数据。脚本兼容项目当前使用的 MySQL 和 SQLite 配置，输出一个便于传输和分析的 ZIP 文件。

脚本只导出数据库中真实存在的表与字段。线上版本缺表或字段时，跳过对应内容，并在数据质量报告中说明，不修改数据库结构，也不写入业务表。

## 交付形式

- 主脚本：`scripts/export_research_dataset.py`
- 测试：`tests/test_research_data_export.py`
- 使用说明：`docs/research_data_export.md`
- 默认输出：`codesense-research-export-<UTC时间>.zip`

脚本从 CodeSense 项目根目录运行，沿用应用现有的 Flask 配置和 `DATABASE_URL`。输出目录可通过命令行参数指定。

## 导出内容

ZIP 至少包含以下文件。相关表不存在时，文件仍保留表头，并在质量报告中记录原因。

### `users.csv`

- 匿名用户 ID
- 用户角色
- 匿名班级 ID
- 注册时间

不导出学号原值、姓名、邮箱、密码、头像路径、会话标识或邀请信息。

### `assignments.csv`

- 匿名作业 ID
- 创建时间、截止时间
- 目标班级数量
- 题目描述长度
- 是否具有三阶段预设

默认不导出题目标题、题目正文、标准答案和测试用例。

### `submissions.csv`

- 匿名用户 ID、匿名作业 ID、匿名提交 ID
- 提交时间
- 分数、状态、语言
- 代码字符数、非空行数
- 反馈字符数

默认不导出代码正文和反馈正文。

### `thinking_sessions.csv`

- 匿名会话、用户和作业 ID
- 当前阶段、状态
- 阶段一得分和提示次数
- 阶段二、阶段三完成状态
- 阶段二提示次数
- 两类 Agent 对话轮次
- 总学习时长、开始时间和完成时间
- 阶段一思路描述长度

使用 `--include-text` 时，增加经过基础脱敏的阶段一思路正文。

### `thinking_stage_logs.csv`

- 匿名日志、会话 ID
- 阶段、事件类型、角色、时间
- 内容长度
- 从 `metadata_json` 中提取的安全结构特征

默认不导出日志正文。使用 `--include-text` 时，增加经过基础脱敏的正文。代码修复、Agent 写代码等事件即使启用文本模式，也不导出代码正文。

### `thinking_presets.csv`

- 匿名作业 ID
- 预设状态与生成时间
- 关键步骤、代码块、干扰块、逐步问答的数量
- 难度配置中可用于分析的轮次数和 Agent 角色类型

不导出参考代码、算法答案正文和完整预设 JSON。

### 辅助文件

- `manifest.json`：导出时间、脚本版本、匿名盐指纹、数据库类型、文件行数和运行参数
- `schema_inventory.csv`：研究相关表实际存在的字段，用于核对线上版本差异
- `data_quality.json`：缺表、缺字段、空值数量、时间范围、关系缺失和跳过项
- `README.txt`：文件用途、隐私说明和交付注意事项

## 匿名化与隐私

脚本每次运行生成随机匿名盐，并使用 HMAC-SHA256 把原始主键转换为稳定的匿名 ID。同一次导出内可以跨表关联，不同导出之间默认无法追踪同一用户。

匿名盐本身不写入 ZIP，只记录不可用于反推的盐指纹。研究需要重复导出并保持 ID 一致时，操作者可通过环境变量 `CODE_SENSE_EXPORT_SALT` 显式提供盐。

文本模式仅做基础脱敏，包括邮箱、手机号、常见学号样式和明显 IP 地址。由于自由文本可能包含无法自动识别的个人信息，脚本默认关闭文本导出，并在启用时打印警告。

## 兼容和失败处理

- 使用 SQLAlchemy 检查数据库表和字段，不依赖 MySQL 专属 SQL。
- 查询按批次迭代，避免一次性载入全部日志和提交。
- 单个可选表缺失时继续导出其他内容。
- 数据库连接失败、输出目录不可写或 ZIP 创建失败时返回非零退出码。
- 导出过程不输出数据库连接串、密钥或原始身份信息。
- 已存在的目标文件不覆盖，除非显式传入 `--overwrite`。

## 命令行接口

```powershell
python scripts/export_research_dataset.py
python scripts/export_research_dataset.py --output-dir research_exports
python scripts/export_research_dataset.py --include-text
python scripts/export_research_dataset.py --output exported.zip --overwrite
```

## 验收条件

1. 在当前开发 SQLite 数据库上运行成功并生成可打开的 ZIP。
2. ZIP 中不含密码、邮箱、Token、数据库连接串和完整代码。
3. 同一原始用户在不同 CSV 中得到相同匿名 ID。
4. 缺少可选表或字段时仍能生成其余文件，并在质量报告中说明。
5. 默认模式不包含思路、对话、代码和反馈正文。
6. `--include-text` 仅增加允许的学习文本，不增加代码类事件正文。
7. 自动化测试覆盖匿名化、敏感字段排除、文本脱敏、缺字段兼容和 ZIP 清单。

