# AI插画版三阶段机制图实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成一张包含教师机器人、真人学生与虚拟学生机器人的高质量论文机制图，同时用确定性排版保证中文准确、无文字图片重叠，并替换两篇Word中的图1。

**Architecture:** imagegen负责生成不含文字的三角色教育插画底图，本地Pillow脚本负责框架、箭头和全部中文。布局吸收Agent4Edu的“状态—行动”分层与EduPlanner的“角色输入—职责—输出”表达，但只呈现本系统已经实现的会话内状态和三阶段活动。脚本输出版本化预览图，经视觉验收后再覆盖论文正式图片并重建Word。

**Tech Stack:** built-in imagegen、Python 3、Pillow、pytest、python-docx、LibreOffice 26.2、Poppler。

## Global Constraints

- 最终画布不低于3200×1800像素，横向16:9，适合Word页面宽度缩放。
- AI插画不得包含文字、字母、数字、水印、品牌标识和错误UI。
- 全部中文使用设计稿中的固定文案，不允许AI改写。
- 教师机器人为蓝色、真人学生居中、虚拟学生机器人为橙色；程序构建阶段使用绿色。
- 必须同时呈现当前会话状态、角色职责、三阶段活动和日志证据边界。
- 不出现“提升能力”“深度理解已经发生”等效果性图标或结论。
- 不覆盖用户的`.tmp/`与`static/uploads/`内容。

---

### Task 1: 生成并验收无文字AI角色底图

**Files:**
- Create: `research/guided_learning_paper/figures/assets/ai_three_role_scene.png`
- Create: `.tmp/illustrated_figure/task1_visual_review.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-21-paper-mechanism-illustration-design.md`；现有教师示意图和论文图1仅作构图参照。
- Produces: 一张可被合成脚本读取的横向PNG，包含左侧蓝色教师机器人、中间真人大学生、右侧橙色虚拟学生机器人，背景干净且不含任何文字。

- [ ] **Step 1: 用built-in imagegen生成第一版角色场景**

Prompt：

```text
Use case: scientific-educational
Asset type: Chinese academic-paper mechanism infographic base illustration
Primary request: Create a polished horizontal educational illustration with three clearly separated characters: a friendly blue teacher robot on the left, a real Chinese university student using a laptop in the center, and a friendly orange virtual-student robot on the right. The teacher robot gestures toward the student as if offering guidance. The real student turns slightly toward the orange robot as if explaining. The orange robot shows curiosity and asks a question. Leave generous clean negative space above, below, and around each character for later diagram labels and arrows.
Style/medium: clean premium flat editorial illustration, subtle depth, rounded geometry, suitable for an academic journal figure; more sophisticated than clip art
Composition/framing: 16:9 landscape, three characters aligned horizontally, full upper bodies visible, balanced spacing, no overlapping characters
Color palette: blue and cool gray on the left, neutral blue-green around the student, warm orange on the right, white background
Constraints: absolutely no text, no letters, no numbers, no labels, no speech bubbles, no logos, no watermark, no charts, no upward-growth icons; do not crop heads or hands
Avoid: childish cartoon, photorealistic faces, busy classroom background, visual clutter, illegible pseudo-text, repeated limbs
```

Expected: teacher robot, real student and virtual-student robot are visually distinct; no generated text appears anywhere.

- [ ] **Step 2: Inspect the generated image at original resolution**

Use `view_image` with `detail="original"`. Record PASS/FAIL for character count, left-center-right order, role gestures, unwanted text, cropped limbs and usable negative space in `.tmp/illustrated_figure/task1_visual_review.md`.

- [ ] **Step 3: Regenerate once with one targeted correction if needed**

If the first version contains pseudo-text, bad anatomy or poor spacing, reuse the same prompt and add exactly one correction such as:

```text
Targeted correction: remove every text-like mark and increase the blank space between all three characters while preserving their colors, identities and left-center-right order.
```

Expected: the selected image passes all Task 1 review items.

- [ ] **Step 4: Save the selected image in the project**

Copy the selected built-in output from its generated-images location to:

```text
research/guided_learning_paper/figures/assets/ai_three_role_scene.png
```

- [ ] **Step 5: Commit the selected AI asset**

```bash
git add research/guided_learning_paper/figures/assets/ai_three_role_scene.png
git commit -m "design: add AI-generated learning-role illustration"
```

### Task 2: 合成论文级框架、中文与重叠检测

**Files:**
- Create: `scripts/compose_guided_learning_illustration.py`
- Create: `tests/test_guided_learning_paper_illustration.py`
- Create: `research/guided_learning_paper/figures/activity_chain_evidence_illustrated.png`

**Interfaces:**
- Consumes: `figures/assets/ai_three_role_scene.png`和设计稿中的固定中文。
- Produces: `compose_figure(asset_path: Path, output_path: Path) -> None`；最终3200×1800 RGB PNG；`layout_boxes() -> dict[str, tuple[int, int, int, int]]`供测试复用。

- [ ] **Step 1: 写入失败的尺寸、文案与重叠测试**

```python
from pathlib import Path

from PIL import Image

from scripts.compose_guided_learning_illustration import COPY, layout_boxes


def test_illustrated_figure_has_fixed_copy_and_non_overlapping_regions():
    required = {
        "状态驱动的三阶段程序设计引导方法",
        "教师型智能体",
        "真实学生",
        "虚拟学生",
        "1 思路外化",
        "2 程序构建",
        "3 讲解纠错",
        "日志不能直接证明：认知质量、学习增益与因果效果",
    }
    assert required <= set(COPY.values())
    boxes = layout_boxes()
    names = list(boxes)
    for index, left_name in enumerate(names):
        lx1, ly1, lx2, ly2 = boxes[left_name]
        for right_name in names[index + 1:]:
            rx1, ry1, rx2, ry2 = boxes[right_name]
            assert lx2 <= rx1 or rx2 <= lx1 or ly2 <= ry1 or ry2 <= ly1


def test_illustrated_figure_is_print_ready():
    image = Image.open(
        Path("research/guided_learning_paper/figures/activity_chain_evidence_illustrated.png")
    )
    assert image.size == (3200, 1800)
    assert image.mode == "RGB"
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
py -m pytest tests/test_guided_learning_paper_illustration.py -q
```

Expected: FAIL because the composition module and output image do not exist.

- [ ] **Step 3: 实现确定性合成脚本**

The script must define:

```python
CANVAS = (3200, 1800)
COPY = {
    "title": "状态驱动的三阶段程序设计引导方法",
    "subtitle": "智能体依据本次会话状态调整支架，学习任务始终由学生完成",
    "teacher": "教师型智能体",
    "teacher_reads": "读取：回答、提示次数、进度、验证结果",
    "teacher_outputs": "输出：提示、诊断、支架",
    "student": "真实学生",
    "student_actions": "表达思路 · 判断结构 · 讲解与修正",
    "virtual_student": "虚拟学生",
    "virtual_actions": "连续追问 · 呈现错误代码",
    "stage1": "1 思路外化",
    "stage1_action": "说明算法步骤与边界",
    "stage2": "2 程序构建",
    "stage2_action": "识别结构并验证修正",
    "stage3": "3 讲解纠错",
    "stage3_action": "向虚拟学生讲解并修正错误",
    "observable": "日志可观察：进入、提示、验证、对话、修正、完成与退出",
    "boundary": "日志不能直接证明：认知质量、学习增益与因果效果",
}
```

`layout_boxes()` must return non-overlapping rectangles for: title, state strip, role scene, stage1, stage2, stage3, observable and boundary. The role scene uses the AI asset as a centered visual layer. Draw rounded panels, directional arrows and stage ribbons after scaling the AI asset with preserved aspect ratio. Use an installed Chinese sans-serif font with explicit fallback search; fail with a clear error if no CJK font is found. Text wrapping must measure rendered width with `ImageDraw.textbbox` rather than fixed character counts.

- [ ] **Step 4: 生成插画版并运行测试**

```powershell
py scripts/compose_guided_learning_illustration.py `
  --asset research/guided_learning_paper/figures/assets/ai_three_role_scene.png `
  --output research/guided_learning_paper/figures/activity_chain_evidence_illustrated.png

py -m pytest tests/test_guided_learning_paper_illustration.py -q
```

Expected: output is exactly3200×1800 RGB and tests pass.

- [ ] **Step 5: 原图视觉复核**

Use `view_image(detail="original")` and verify:

- all Chinese strings match `COPY` character for character;
- no text touches a character, panel border or arrow;
- the state-to-support relation is readable before the three stages;
- the student remains the central actor;
- the evidence boundary is visually weaker than the activity flow;
- the figure remains legible when downscaled to approximately1600 pixels wide.

- [ ] **Step 6: Commit the composition code, test and preview**

```bash
git add scripts/compose_guided_learning_illustration.py tests/test_guided_learning_paper_illustration.py research/guided_learning_paper/figures/activity_chain_evidence_illustrated.png
git commit -m "design: compose illustrated adaptive-learning framework"
```

### Task 3: 替换论文图片并重建两份Word

**Files:**
- Modify: `research/guided_learning_paper/figures/activity_chain_evidence.png`
- Regenerate: `research/guided_learning_paper/paper_core_zh.docx`
- Regenerate: `research/guided_learning_paper/paper_practice_zh.docx`
- Modify: `research/guided_learning_paper/revision_log.md`

**Interfaces:**
- Consumes: Task 2验收通过的`activity_chain_evidence_illustrated.png`。
- Produces: 两份引用新机制图的最终Word和对应视觉验收记录。

- [ ] **Step 1: 非破坏性保存预览并覆盖正式图**

Copy the approved preview bytes to `activity_chain_evidence.png`; retain `activity_chain_evidence_illustrated.png` as the versioned source output.

- [ ] **Step 2: 运行图像与论文测试**

```powershell
py -m pytest tests/test_guided_learning_paper_illustration.py tests/test_guided_learning_paper_plots.py tests/test_guided_learning_paper_docx.py -q
```

Expected: all tests pass.

- [ ] **Step 3: 重建两份Word**

```powershell
py scripts/build_guided_learning_paper_docx.py --input-md research/guided_learning_paper/manuscript_core_zh.md --output-docx research/guided_learning_paper/paper_core_zh.docx
py scripts/build_guided_learning_paper_docx.py --input-md research/guided_learning_paper/manuscript_practice_zh.md --output-docx research/guided_learning_paper/paper_practice_zh.docx
```

Expected: both files exceed100KB and preserve blank author metadata.

- [ ] **Step 4: 渲染并检查包含图1的页面**

Use LibreOffice with an isolated profile to convert each DOCX to PDF, then use the bundled real `pdftoppm.exe` at120 DPI. Inspect every page, with original-resolution checks on the two pages containing图1. Verify no clipping, overlap, pseudo-text or unreadable small labels.

- [ ] **Step 5: 更新修订日志并运行全量测试**

Record the AI asset prompt, deterministic Chinese strategy, final pixel size, Word page counts and visual review result in `revision_log.md`.

```powershell
py -m pytest tests -q --disable-warnings
git diff --check
```

Expected: all tests pass and no whitespace errors.

- [ ] **Step 6: Commit final figure and documents**

```bash
git add research/guided_learning_paper/figures/activity_chain_evidence.png research/guided_learning_paper/paper_core_zh.docx research/guided_learning_paper/paper_practice_zh.docx research/guided_learning_paper/revision_log.md
git commit -m "docs: publish AI-illustrated mechanism figure"
```

## Final Verification

- [ ] Figure visibly contains one teacher robot, one real student and one virtual-student robot.
- [ ] Figure follows a state/input → role/action → three-stage activity → evidence-boundary hierarchy.
- [ ] Every Chinese string matches the approved copy exactly.
- [ ] No text overlaps an illustration, arrow or panel border.
- [ ] No unverified learning-effect claim appears in the image.
- [ ] Both DOCX files render with a readable figure at page width.
- [ ] Full pytest suite passes.
- [ ] Commits exclude `.tmp/` and `static/uploads/`.
