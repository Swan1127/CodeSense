# Task 2 报告：活动链总览图改为“状态—决策—支架”结构

## 完成内容

图 1 已改为横向的“状态—决策—支架”结构，标题为“状态驱动的三阶段程序设计引导方法”。视觉中心放在学生完成的三阶段学习方法，而不是 CodeSense 平台。

上层从左到右展示：可观察的学生状态、会话内智能体决策、适配的学习支架。状态输入包括自然语言回答、提示次数、当前进度、错误类型和对话历史；决策层说明智能体仅在本次会话内诊断状态并选择下一步，不建立跨作业学习者画像；支架层列出提示强度、追问对象、反馈内容和阶段推进条件。

中层保留并重写三阶段活动：思路外化、程序构建、讲解纠错。第三阶段明确标注“教师角色—真实学生—虚拟学生”，描述为围绕学生讲解和错误代码的协同追问，未将其绘制成两个彼此自治的系统。

下层将过程日志的证据边界拆为两个并列区域。实线框列出日志可观察的采用、阶段推进、回退、退出及相邻操作转换；虚线框说明日志不能直接观察认知质量和学习增益，后两者需要内容编码或后续对照研究验证。

## TDD 记录

先在 `tests/test_guided_learning_paper_plots.py` 新增 `test_activity_chain_figure_is_landscape_and_readable`，再运行该单测。旧图测试失败，实际尺寸为 2850×1561，宽度未达到 3000 像素的要求。随后才修改绘图函数。

实现后，该测试通过。正式生成的 `activity_chain_evidence.png` 尺寸为 3175×1907，满足横向、宽度不低于 3000 像素、高度不低于 1700 像素的要求。

## 视觉检查与修正

使用原始分辨率查看生成图。第一次检查发现从“适配的学习支架”指向三个阶段的两条斜箭头穿过了中心说明文字。已删除这两条会造成遮挡的箭头，保留支架到第三阶段的垂直连线，并用各阶段内的支架说明表达其贯穿作用。第二次原始分辨率检查确认标题、说明、阶段文字、箭头和虚线边界均未出现裁切或重叠。

图中以文字、实线和虚线共同区分信息层级，因此在黑白打印时仍可区分已观察的日志证据与未直接测得的认知或学习增益。

## 验证

- 定向红灯：`py -m pytest tests/test_guided_learning_paper_plots.py::test_activity_chain_figure_is_landscape_and_readable -q`，旧图失败，原因符合预期。
- 定向绿灯：同一命令在实现后通过。
- 生成：`py scripts/plot_guided_learning_paper.py` 成功更新全部论文图，活动链图非空。
- 绘图测试：`py -m pytest tests/test_guided_learning_paper_plots.py -q`，2 通过。
- 相关论文测试：`py -m pytest tests/test_guided_learning_paper_plots.py tests/test_guided_learning_paper_content.py tests/test_guided_learning_paper_docx.py tests/test_guided_learning_research_analysis.py -q`，25 通过。

## 自审与范围

已检查变更内容、PNG 尺寸和原始分辨率渲染。图中没有将 CodeSense 放在视觉中心，也没有把日志行为写成认知质量或学习增益。未修改 Task 1 的审计或矩阵文件，未触碰冻结结果；`.tmp/` 与 `static/uploads/` 保持未跟踪状态且不纳入提交。

本任务提交仅包含绘图脚本、绘图测试、生成的活动链 PNG 和本报告。

## 审查修正补充（2026-07-20）

### 修正内容

审查指出支架连接器只落到第三阶段。原因是绘图函数只保留了 `arrow((0.825, 0.69), (0.825, 0.55))` 这一条支架到阶段的连线。现改为从“适配的学习支架”引出一条无箭头的垂直线，接入位于三个阶段上方的水平轨道；轨道再用三条短垂直箭头分别连接思路外化、程序构建和讲解纠错。标签改为“基于当前状态的支架贯穿三个阶段”，连接器不再穿过说明文字。

可观察状态框扩为三行：自然语言回答、提示次数、当前进度/得分；错误/未答步骤、代码块错误与修正结果；对话/教学记录。原有尺寸测试更名为 `test_activity_chain_figure_has_revised_landscape_canvas`，避免把尺寸检查称作可读性检查。另加 `test_activity_chain_source_labels_cover_required_state_and_shared_support`，只核验审查要求的状态标签和共享支架标签。

### RED/GREEN 证据

新增标签断言先运行：

`py -m pytest tests/test_guided_learning_paper_plots.py::test_activity_chain_source_labels_cover_required_state_and_shared_support -q`

旧实现失败，首个缺失标签为“当前进度/得分”。补全状态标签和共享支架标签后，同一测试通过。改名后的画布测试 `test_activity_chain_figure_has_revised_landscape_canvas` 也通过。

### 生成、检查与测试

重新运行 `py scripts/plot_guided_learning_paper.py` 后，`activity_chain_evidence.png` 为 3175×1907 像素。使用原始分辨率查看后确认：水平支架轨道及其三条落箭头清楚指向三个阶段；新增状态字段完整可读；标题、箭头和证据边界没有裁切或重叠。

- 专项绘图测试：`py -m pytest tests/test_guided_learning_paper_plots.py -k activity_chain -q`，2 通过、1 跳过。
- 绘图测试文件：`py -m pytest tests/test_guided_learning_paper_plots.py -q`，3 通过。
- 相关论文测试：`py -m pytest tests/test_guided_learning_paper_plots.py tests/test_guided_learning_paper_content.py tests/test_guided_learning_paper_docx.py tests/test_guided_learning_research_analysis.py -q`，26 通过。

实现提交：`0653be0fef944ee3301a0ddf1829d295ad63d823`（`fix: show shared adaptive support across stages`）。本次实现改动包含绘图脚本、绘图测试和活动链 PNG；`.tmp/` 与 `static/uploads/` 继续保持未跟踪状态。
