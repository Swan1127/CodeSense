# 三阶段引导式学习论文工作区

本目录保存CodeSense三阶段引导式学习论文的分析结果、证据审计和双轨稿件。第一版 `manuscript_zh.md` 与 `paper_zh.docx` 保留作修订对照，不由新版生成流程覆盖。

## 主要文件

- `manuscript_core_zh.md` / `paper_core_zh.docx`：中文核心期刊导向稿；
- `manuscript_practice_zh.md` / `paper_practice_zh.docx`：计算机教育实践稿；
- `literature_matrix.md`：中英文研究证据矩阵和可外推边界；
- `reference_paper_audit.md`：11篇外部智能体论文的全文核验、来源分级和不可外推边界；
- `peer_review_audit_v2.md`：第二轮模拟外审；
- `revision_log.md`：第一版问题、改动、证据和剩余限制；
- `next_study_protocol.md`：下一轮阶梯楔形研究方案；
- `concurrency_evaluation_protocol.md`：并发评测的执行闸门、停止条件和核验顺序；
- `simulation_evaluation_protocol.md`：288条正式仿真、96条双教师盲审、统计方法和证据边界；
- `data_provenance.md`：数据快照、版本边界和隐私说明；
- `results/`：分析脚本生成的冻结结果；
- `figures/`：正文与附录图片。

当前两篇修订稿均把智能体限定为“会话内、状态驱动的微观调节”。核心稿突出活动链、研究问题和行为证据，实践稿突出教师可复用的支架规则。用户提供的提纲、示例论文与师生智能体PPT只作为结构和角色表达参照，未核实的模型配置、认知指标与伦理编号不进入正文。

## 复现命令

在仓库根目录运行：

```powershell
py scripts/analyze_guided_learning_research.py `
  --zip-path 'C:\path\to\codesense-research-export-20260716T090300Z.zip' `
  --output-dir research/guided_learning_paper/results

py scripts/plot_guided_learning_paper.py `
  --results-dir research/guided_learning_paper/results `
  --output-dir research/guided_learning_paper/figures

py scripts/build_guided_learning_paper_docx.py `
  --input-md research/guided_learning_paper/manuscript_core_zh.md `
  --output-docx research/guided_learning_paper/paper_core_zh.docx

py scripts/build_guided_learning_paper_docx.py `
  --input-md research/guided_learning_paper/manuscript_practice_zh.md `
  --output-docx research/guided_learning_paper/paper_practice_zh.docx
```

正式测试使用 `py -m pytest tests -q`。仓库根目录的 `test_results.txt` 是UTF-16文本，直接运行不限定路径的pytest会被doctest收集器误读，因此不作为测试入口。

## 数据和投稿边界

匿名研究ZIP保存在仓库外，不提交到Git。仓库也不得加入匿名密钥、数据库配置、学生代码、对话正文或可重新识别个体的原始事件序列。正文数字必须来自 `results/` 下的冻结结果。

匿名化不等于伦理程序已经完成。正式投稿前，研究团队仍需确认伦理审批或书面豁免、研究同意、作者顺序与单位、基金、利益冲突和数据可获得性声明。当前日志只能支持采用、路径、过程摩擦和提交关联分析，不能支持学习增益或因果判断。两篇稿件使用同一数据，选择投稿路线时应避免重复发表，并向编辑部说明彼此关系。

设计与执行记录见：

- `docs/superpowers/specs/2026-07-16-guided-learning-paper-revision-design.md`
- `docs/superpowers/plans/2026-07-16-guided-learning-paper-revision.md`
- `docs/superpowers/plans/2026-07-20-adaptive-agent-paper-reference-revision.md`
