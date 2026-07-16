# CodeSense 研究数据导出说明

这个脚本用于从 CodeSense 线上数据库提取论文研究所需的数据。它只查询数据库，不启动网站、不初始化表，也不会修改业务数据。

## 一、放置位置

请把以下两个文件放到线上 CodeSense 项目的对应位置：

- `research_export.py`：项目根目录
- `scripts/export_research_dataset.py`：`scripts` 目录

线上项目需要能够正常读取现有的 `config.py`、`models.py` 和数据库环境变量。通常不需要安装新依赖。

## 二、推荐运行方式

先进入 CodeSense 项目根目录。

Windows PowerShell：

```powershell
py scripts/export_research_dataset.py
```

Linux：

```bash
python3 scripts/export_research_dataset.py
```

脚本默认在 `research_exports` 目录生成文件：

```text
codesense-research-export-20260716T080000Z.zip
```

这个 ZIP 就是需要发回分析的文件。

## 三、数据库配置

脚本沿用平台的 Flask 配置。生产环境一般已经设置：

```text
DATABASE_URL=mysql+pymysql://...
FLASK_CONFIG=production
```

不要把数据库连接串写进命令，也不要把 `.env` 文件一并发送。

如果平台平时通过其他方式设置这些环境变量，请使用同一用户和同一运行环境执行脚本。

## 四、默认隐私保护

默认导出不包含：

- 学号、姓名、邮箱、密码和登录会话；
- 班级名称、作业标题和题目正文；
- 学生提交的完整代码；
- AI 反馈、评语和对话正文；
- 标准答案、测试用例和数据库连接信息。

用户、作业、提交、会话和日志 ID 会经过 HMAC-SHA256 匿名化。同一个 ZIP 内仍然可以跨表关联，无法直接还原原始 ID。

每次运行默认使用新的随机盐，因此两次导出的匿名 ID 不一致。如果后续需要增量导出并保持 ID 一致，可以设置固定盐：

Windows PowerShell：

```powershell
$env:CODE_SENSE_EXPORT_SALT='请换成一段至少32位的随机字符串'
py scripts/export_research_dataset.py
```

Linux：

```bash
export CODE_SENSE_EXPORT_SALT='请换成一段至少32位的随机字符串'
python3 scripts/export_research_dataset.py
```

固定盐不要发给任何人，也不要放入 ZIP。

## 五、需要研究学习文本时

如果后续需要分析学生的思路表达和非代码对话，可以运行：

```powershell
py scripts/export_research_dataset.py --include-text
```

该模式会自动遮盖常见邮箱、手机号、IP 地址和连续数字形式的学号。代码修复、Agent 写代码等事件的正文仍然不会导出。

自由文本无法做到百分之百自动脱敏。启用这个选项后，请先人工检查 ZIP 内的 `thinking_sessions.csv` 和 `thinking_stage_logs.csv`，再发送给研究人员。

第一轮建议先运行默认模式。数据结构和样本量确认后，再决定是否需要文本。

## 六、其他参数

指定输出目录：

```powershell
py scripts/export_research_dataset.py --output-dir D:\research_exports
```

指定完整文件名：

```powershell
py scripts/export_research_dataset.py --output D:\research_exports\codesense-data.zip
```

覆盖已经存在的文件：

```powershell
py scripts/export_research_dataset.py --output D:\research_exports\codesense-data.zip --overwrite
```

脚本默认拒绝覆盖已有 ZIP，避免误删上一次导出。

## 七、ZIP 内容

- `users.csv`：匿名用户、角色、匿名班级和注册时间；
- `assignments.csv`：匿名作业、难度、时间和是否有三阶段预设；
- `submissions.csv`：成绩、提交时间、语言、代码规模和沙箱结果；
- `thinking_sessions.csv`：阶段进度、提示次数、得分、对话轮次和学习时长；
- `thinking_stage_logs.csv`：各阶段事件、角色、时间和安全的元数据统计；
- `thinking_presets.csv`：预设规模、费曼轮次和 Agent 角色类型；
- `schema_inventory.csv`：线上数据库实际存在的相关字段；
- `manifest.json`：脚本版本、导出时间和各文件行数；
- `data_quality.json`：缺表、缺字段、空值、时间范围和孤立关系检查；
- `README.txt`：ZIP 内的简要隐私说明。

如果线上版本缺少某个可选字段，脚本会留下空值并在 `data_quality.json` 中记录。缺少某个可选表时，其他表仍会继续导出。

## 八、发送前检查

1. 确认脚本最后显示 `Research archive created`。
2. 打开 ZIP，确认其中包含上述十个文件。
3. 默认模式下，随机打开 CSV 检查是否只有匿名 ID。
4. 不要发送 `.env`、数据库备份、日志目录或固定匿名盐。
5. 只发送最终生成的 ZIP。

