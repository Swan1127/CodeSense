# 三阶段引导式学习仿真实验协议

版本：1.0  
冻结日期：2026-07-22

## 1. 研究目的与证据边界

本实验用于检查三阶段引导式学习框架在不同算法任务和学习困难画像下，能否稳定执行“理解问题—组织解法—外化与检验”的活动链，并减少过早给出完整答案。实验对象是由大语言模型驱动的虚拟学生不是现实学生。仿真结果只能支持机制可执行性、交互过程和回答约束方面的判断，不能证明真实学习增益，也不能替代课堂对照实验。

线上课堂日志与仿真轨迹分别保存、分别分析。发往智谱接口的内容仅包括算法题描述、虚拟学生画像、冻结提示词和仿真对话，不包含真实学生身份、作业代码、评分、课堂日志或其他可重新识别信息。

## 2. 比较条件

- C0：直接回答式助手；
- C1：顺序固定、不能依据学生状态调整的三阶段助手；
- C2：完整的状态驱动三阶段框架；
- A1—A3：分别移除关键调节机制的消融条件，均与同一任务和画像下的 C2 配对比较。

学习者生成器、C0/C1 系统生成器和自动评审器使用同一基础模型 glm-4.5-flash，但采用彼此隔离的提示词和上下文。使用同一基础模型有利于控制模型家族差异，也可能带来共享偏差；论文必须把这一点列为限制，不得把自动评审视为独立的人类判断。

## 3. 冻结样本矩阵

正式主实验由以下两部分组成：

- 核心比较：12 道正式题 × 6 类虚拟学生画像 × 3 个条件 × 1 次运行，共 216 条轨迹；
- 消融比较：6 道冻结题 × 4 类冻结画像 × 3 个消融条件 × 1 次运行，共 72 条轨迹；
- 正式主实验合计 288 条轨迹。

资源允许时可以追加每个单元三次重复的扩展实验，但扩展实验必须另建输出目录并单独报告。重复轨迹先在“题目×画像×条件”单元内求均值，不能被写成多名学习者或多个独立样本。

每条轨迹最多包含 8 次系统响应。技术失败、格式失败、达到轮次上限以及对框架不利但有效的轨迹都要保留。不得调参后保留旧结果，也不得只重跑不利轨迹。开发测试和正式烟雾测试只检查链路，不进入正式证据。

## 4. 指标与统计

机制指标包括任务完成、困难状态恢复、完整代码泄漏、完整步骤过早泄漏、提示重复、阶段顺序异常、系统响应数和技术失败。所有指标分别报告，不构造综合优越性分数。

核心比较为 C2 对 C0、C2 对 C1；消融比较为 A1/A2/A3 分别对相同任务和画像下的 C2。分析单元是配对后的“题目×画像”单元。采用固定随机种子的配对簇自助法计算均值差及百分位 95% 置信区间，以配对符号翻转检验给出双侧 p 值，并用 Holm 方法控制同一比较族的多重检验。二元指标同时给出风险比；离散度不为零时给出标准化配对效应。

技术失败率按条件、题目难度和画像单独切片。主分析保留所有正式轨迹；必要时可补充“仅技术有效轨迹”敏感性分析，但不得用该分析替换完整样本结果。

## 5. 双教师盲审与自动评审

从正式轨迹中按条件、难度和画像分层抽取 96 条：C0、C1、C2 各 24 条，A1、A2、A3 各 8 条。盲审表只显示匿名编号、题目、可观察画像描述和对话，不显示条件、轨迹编号或研究者预期。

两位教师独立完成全部 96 条评分。六个序数维度采用 1—5 分，两个泄漏判断采用 0/1。序数维度报告二次加权 Cohen κ，二元判断报告普通 Cohen κ。自动评审与两位教师均值之间报告 Spearman 相关和平均绝对误差。序数维度要求 Spearman 相关不低于0.60且平均绝对误差不高于1.0；二元判断要求相关不低于0.60且平均绝对误差不高于0.25。任一门槛未达到时，相应自动评审结果只能标记为补充证据。

## 6. 上游测试说明

智谱 upstream 连通性、重试和并发诊断只用于决定串行执行、超时和恢复策略，不属于论文实验，不进入框架优越性、机制效果或学习效果的论证。

## 7. 复现命令

以下命令在仓库根目录执行；本地环境文件路径按实际部署位置填写。正式原始输出不提交到 Git。

~~~powershell
py scripts/run_guided_learning_simulation.py --mode development --matrix core --max-trajectories 12 --output-dir research_exports/simulation/development --env-file C:/path/to/.env
py scripts/run_guided_learning_simulation.py --mode formal --matrix core --max-trajectories 1 --output-dir research_exports/simulation/formal-smoke --env-file C:/path/to/.env
py scripts/run_guided_learning_simulation.py --mode formal --matrix all --output-dir research_exports/simulation/formal-288 --env-file C:/path/to/.env --resume
py scripts/score_guided_learning_simulation.py --input research_exports/simulation/formal-288 --output-dir research_exports/simulation/scored
py scripts/judge_guided_learning_simulation.py --input research_exports/simulation/formal-288 --output research_exports/simulation/scored/automatic_ratings.jsonl --resume
py scripts/build_simulation_teacher_packet.py --input research_exports/simulation/formal-288 --output-dir research_exports/simulation/review
py scripts/import_simulation_teacher_ratings.py --packet research_exports/simulation/review/teacher_1.xlsx --packet research_exports/simulation/review/teacher_2.xlsx --key research_exports/simulation/review/blinding_key.csv --output research_exports/simulation/scored/teacher_ratings.csv
py scripts/analyze_guided_learning_simulation.py --metrics research_exports/simulation/scored/trajectory_metrics.csv --teacher-ratings research_exports/simulation/scored/teacher_ratings.csv --automatic-ratings research_exports/simulation/scored/automatic_ratings.jsonl --blinding-key research_exports/simulation/review/blinding_key.csv --output-dir research_exports/simulation/analysis
py scripts/plot_guided_learning_simulation.py --results-dir research_exports/simulation/analysis --output-dir research_exports/simulation/figures
~~~

## 8. 投稿前检查

论文中必须明确区分真实课堂行为证据和仿真机制证据；不得将 288 条轨迹称为 288 名学生，不得使用因果措辞解释课堂日志或仿真差异。教师评分未返回前，应在稿件中标为“待完成”，不能由研究者或模型代填。
