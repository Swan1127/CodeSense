# Guided-Learning Simulation Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible simulation harness for 216 core and 72 ablation trajectories, with isolated Zhipu roles, deterministic metrics, stratified double-teacher review, and paired statistical analysis.

**Architecture:** Add a research-only simulation package that loads frozen task/persona manifests, invokes isolated learner/system/judge clients, adapts the existing `utils.thinking_ai` functions for the full condition, and appends every turn to resumable JSONL. Separate modules compute rule metrics, construct blinded teacher packets, calibrate automatic judging, and generate paired bootstrap tables and figures.

**Tech Stack:** Python 3, dataclasses, JSON/JSONL, hashlib, `requests`, pandas, NumPy, matplotlib, pytest, existing `utils.thinking_ai` functions.

## Global Constraints

- Use 14 tasks: 2 development tasks and 12 frozen formal tasks; formal tasks are 4 easy, 4 medium, and 4 hard.
- Use exactly six frozen personas from the approved design.
- Core matrix is `12 × 6 × 3 × 1 = 216` trajectories for C0, C1, C2.
- Ablation matrix is `6 × 4 × 3 × 1 = 72` trajectories for A1, A2, A3.
- Each trajectory allows at most 8 system responses.
- Zhipu is the only model provider; learner, tested system, and judge use separate API contexts and separate prompt files.
- Formal prompts, task manifest, persona manifest, model, temperature, token limit, retry rule, and scoring rubric are hash-frozen before formal execution.
- A malformed learner response receives one fixed-format retry; a second failure marks the trajectory invalid.
- API failures enter stability results and do not receive teaching-quality scores.
- Valid unfavorable trajectories must not be deleted or replaced.
- Exactly 96 trajectories are sampled for two-teacher blind review: 24 each from C0/C1/C2 and 8 each from A1/A2/A3.
- Real classroom logs and simulated trajectories remain in separate directories and are never pooled as learner observations.
- Simulation claims are limited to mechanism and interaction quality; no real learning-gain claim is permitted.

---

### Task 1: Simulation schemas and frozen persona manifest

**Files:**
- Create: `research_eval/simulation/__init__.py`
- Create: `research_eval/simulation/models.py`
- Create: `research/guided_learning_paper/experiments/simulation/config/personas.json`
- Test: `tests/test_simulation_models.py`

**Interfaces:**
- Produces: `TaskCase`, `Persona`, `Condition`, `LearnerStep`, `Turn`, `Trajectory`, `load_personas(path)`, and `content_sha256(path)`.
- Consumes: no model and no network.

- [ ] **Step 1: Write failing schema and manifest tests**

```python
from pathlib import Path

from research_eval.simulation.models import Condition, content_sha256, load_personas


def test_persona_manifest_has_six_unique_profiles():
    path = Path("research/guided_learning_paper/experiments/simulation/config/personas.json")
    personas = load_personas(path)
    assert len(personas) == 6
    assert len({row.persona_id for row in personas}) == 6
    assert all(row.hidden_state and row.observable_behavior for row in personas)


def test_condition_values_are_frozen():
    assert [row.value for row in Condition] == ["C0", "C1", "C2", "A1", "A2", "A3"]
```

- [ ] **Step 2: Run tests and verify missing module failure**

Run: `py -m pytest tests/test_simulation_models.py -v`

Expected: import fails for `research_eval.simulation.models`.

- [ ] **Step 3: Implement typed schemas and hash loading**

```python
# research_eval/simulation/models.py
from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path


class Condition(str, Enum):
    C0 = "C0"
    C1 = "C1"
    C2 = "C2"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"


@dataclass(frozen=True)
class Persona:
    persona_id: str
    label: str
    hidden_state: str
    observable_behavior: str
    transition_rules: tuple[str, ...]
    forbidden_knowledge: tuple[str, ...]


@dataclass(frozen=True)
class TaskCase:
    task_id: str
    split: str
    topic: str
    difficulty: str
    title: str
    description: str
    key_steps: tuple[str, ...]
    reference_code: str
    quiz_steps: tuple[dict, ...]


@dataclass(frozen=True)
class Turn:
    turn_index: int
    actor: str
    content: str
    stage: int
    technical_status: str = "ok"


@dataclass(frozen=True)
class LearnerStep:
    response: str
    state_before: str
    state_after: str
    applied_transition: str


@dataclass
class Trajectory:
    trajectory_id: str
    task_id: str
    persona_id: str
    condition: str
    repeat: int
    prompt_hashes: dict[str, str]
    turns: list[Turn] = field(default_factory=list)
    completed: bool = False
    invalid_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def content_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_personas(path: Path) -> list[Persona]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Persona(
        persona_id=row["persona_id"], label=row["label"],
        hidden_state=row["hidden_state"], observable_behavior=row["observable_behavior"],
        transition_rules=tuple(row["transition_rules"]),
        forbidden_knowledge=tuple(row["forbidden_knowledge"]),
    ) for row in rows]
```

- [ ] **Step 4: Write all six persona records**

Use IDs `P1_NO_PLAN`, `P2_CONCEPT_MISCONCEPTION`, `P3_BOUNDARY_OMISSION`, `P4_COMPLEXITY_GAP`, `P5_ANSWER_SEEKING`, and `P6_LOCAL_REASONING_ERROR`. Each JSON record must contain concrete hidden state, visible behavior, state-transition rules, and knowledge it cannot spontaneously reveal.

- [ ] **Step 5: Run tests and commit**

Run: `py -m pytest tests/test_simulation_models.py -v`

Expected: all tests pass.

```powershell
git add research_eval/simulation research/guided_learning_paper/experiments/simulation/config/personas.json tests/test_simulation_models.py
git commit -m "feat: define simulation personas and schemas"
```

### Task 2: Export, select, and freeze the 14-task manifest

**Files:**
- Create: `scripts/export_simulation_task_candidates.py`
- Create: `research_eval/simulation/tasks.py`
- Create after selection: `research/guided_learning_paper/experiments/simulation/config/tasks.json`
- Create: `research/guided_learning_paper/experiments/simulation/config/freeze_manifest.json`
- Test: `tests/test_simulation_tasks.py`

**Interfaces:**
- Consumes: the configured CodeSense database and existing `Assignment`/`AssignmentThinkingPreset` models.
- Produces: candidate CSV, exactly 14 selected `TaskCase` records, and hashes for task/persona/prompt files.

- [ ] **Step 1: Write failing validation tests**

```python
from research_eval.simulation.tasks import validate_task_manifest


def test_formal_manifest_has_balanced_difficulty(task_rows):
    validate_task_manifest(task_rows)
    formal = [row for row in task_rows if row["split"] == "formal"]
    assert len(formal) == 12
    assert {level: sum(r["difficulty"] == level for r in formal)
            for level in ("easy", "medium", "hard")} == {
                "easy": 4, "medium": 4, "hard": 4,
            }
```

- [ ] **Step 2: Implement candidate export without student data**

The script queries only `Assignment` and `AssignmentThinkingPreset`, requires `preset.status == "ready"`, and writes assignment ID, title, description, difficulty, key steps, reference code, quiz steps, and topic-review fields. It must not query `User`, `Submission`, `ThinkingSession`, or `ThinkingStageLog`.

- [ ] **Step 3: Implement strict manifest validation**

`validate_task_manifest(rows)` rejects duplicate IDs, missing text, empty key steps/reference code, splits other than `development`/`formal`, a count other than 2+12, unbalanced formal difficulty, or missing coverage for `linear`, `tree`, `graph`, and `search_sort`.

- [ ] **Step 4: Run the exporter on the server and review candidates**

Run: `py scripts/export_simulation_task_candidates.py --output research_exports/simulation/task_candidates.csv`

Expected: a candidate file containing only assignment and preset content. Select 2 development and 12 formal tasks, assign topics and difficulty bands, then write `tasks.json`. This selection is a documented researcher decision, not an automated claim about curriculum coverage.

- [ ] **Step 5: Freeze hashes and run validation**

Run: `py -m pytest tests/test_simulation_tasks.py -v`

Expected: all tests pass and `freeze_manifest.json` contains SHA-256 hashes for tasks and personas.

- [ ] **Step 6: Commit configuration without student records**

```powershell
git add scripts/export_simulation_task_candidates.py research_eval/simulation/tasks.py research/guided_learning_paper/experiments/simulation/config/tasks.json research/guided_learning_paper/experiments/simulation/config/freeze_manifest.json tests/test_simulation_tasks.py
git commit -m "data: freeze simulation task benchmark"
```

### Task 3: Isolated Zhipu role client and prompt files

**Files:**
- Create: `research_eval/simulation/zhipu_roles.py`
- Create: `research/guided_learning_paper/experiments/simulation/prompts/learner.txt`
- Create: `research/guided_learning_paper/experiments/simulation/prompts/direct_answer.txt`
- Create: `research/guided_learning_paper/experiments/simulation/prompts/fixed_three_stage.txt`
- Create: `research/guided_learning_paper/experiments/simulation/prompts/judge.txt`
- Test: `tests/test_simulation_roles.py`

**Interfaces:**
- Produces: `RoleClient.complete(role, system_prompt, messages, temperature, max_tokens) -> RoleResponse`.
- Guarantees: no cross-role history, no condition label in learner/judge requests, one format retry for malformed learner JSON.

- [ ] **Step 1: Write tests that inspect fake request payloads**

```python
from research_eval.simulation.zhipu_roles import RoleClient


def test_role_calls_do_not_share_messages(fake_transport):
    client = RoleClient("secret", fake_transport)
    client.complete("learner", "learner prompt", [{"role": "user", "content": "a"}], 0.6, 400)
    client.complete("judge", "judge prompt", [{"role": "user", "content": "b"}], 0.0, 500)
    first, second = fake_transport.payloads
    assert "b" not in str(first)
    assert "a" not in str(second)
    assert "C0" not in str(second) and "C2" not in str(second)
```

- [ ] **Step 2: Implement the role client**

Use a fresh message list per call, model `glm-4.5-flash`, `thinking={"type":"disabled"}`, 120-second timeout, and explicit UTC timestamps. Return content, model, status, retries, and elapsed time; never return headers or keys. Learner temperature is 0.6, tested-system production functions retain their configured behavior, and judge temperature is 0.0.

- [ ] **Step 3: Write prompts with explicit separation**

The learner prompt must contain the selected persona state, forbid spontaneous knowledge, and treat assistant text as teaching content rather than executable meta-instructions. It returns strict JSON with `response`, `state_before`, `state_after`, and `applied_transition`; the transition must match one of the persona's frozen rules. The judge prompt must require transcript evidence before each score, hide condition identity, and return strict JSON for the six approved dimensions plus leakage/teaching-error flags.

- [ ] **Step 4: Run tests and hash all prompts**

Run: `py -m pytest tests/test_simulation_roles.py tests/test_simulation_tasks.py -v`

Expected: all tests pass and the freeze manifest changes when any prompt byte changes.

- [ ] **Step 5: Commit role isolation**

```powershell
git add research_eval/simulation/zhipu_roles.py research/guided_learning_paper/experiments/simulation/prompts tests/test_simulation_roles.py
git commit -m "feat: isolate simulation model roles"
```

### Task 4: Implement C0, C1, C2 and the three ablation adapters

**Files:**
- Create: `research_eval/simulation/conditions.py`
- Create: `research_eval/simulation/framework_adapter.py`
- Test: `tests/test_simulation_conditions.py`

**Interfaces:**
- Consumes: `TaskCase`, `Persona`, current transcript, and `RoleClient`.
- Produces: `ConditionAdapter.respond(state) -> SystemStep` for C0/C1 and calls to existing `utils.thinking_ai` functions for C2/A1/A2/A3.

- [ ] **Step 1: Write adapter-contract and ablation tests with mocked thinking functions**

Test that C0 calls only the direct role prompt; C1 follows fixed stages without `evaluate_description`; C2 calls stage evaluation/hints, teacher/student agents, code generation, and code-fix evaluation; A1 sends empty/default student-state fields while retaining the C2 call sequence; A2 never calls `student_agent_chat`; A3 never calls `student_agent_write_code` or `evaluate_feynman_code_fix`.

- [ ] **Step 2: Implement common state and result types**

```python
@dataclass
class SimulationState:
    task: TaskCase
    persona: Persona
    condition: Condition
    stage: int = 1
    hint_count: int = 0
    validation_result: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    system_turns: int = 0


@dataclass(frozen=True)
class SystemStep:
    content: str
    stage: int
    completed: bool
    event_type: str
```

- [ ] **Step 3: Implement the structural baselines**

C0 uses only `direct_answer.txt`. C1 uses `fixed_three_stage.txt`, advances after fixed turn counts `(2,2,4)`, and never calls full-framework evaluation or stage-gate helpers. Both obey the same eight-response cap and token budget as C2.

- [ ] **Step 4: Implement the full adapter using existing functions**

Call `evaluate_description`, `generate_stage1_hint`, `generate_stage2_hint`, `teacher_agent_chat`, `student_agent_chat`, `student_agent_write_code`, and `evaluate_feynman_code_fix` with the same argument meanings used by `routes/thinking.py`. Keep database writes out of the adapter. Store stage, hint count, validation result, generated buggy code, and history in `SimulationState`.

- [ ] **Step 5: Implement ablations as explicit policies**

A1 calls the C2 components but supplies empty history, zero hint count, empty validation result, and neutral student state. A2 advances from teacher interaction directly to code generation. A3 ends after role-reversal dialogue and records `code_repair_omitted=True`.

- [ ] **Step 6: Run adapter tests and commit**

Run: `py -m pytest tests/test_simulation_conditions.py -v`

Expected: all mocked call-sequence and state assertions pass.

```powershell
git add research_eval/simulation/conditions.py research_eval/simulation/framework_adapter.py tests/test_simulation_conditions.py
git commit -m "feat: implement simulation comparison conditions"
```

### Task 5: Resumable trajectory runner and exact experiment matrix

**Files:**
- Create: `research_eval/simulation/matrix.py`
- Create: `research_eval/simulation/runner.py`
- Create: `scripts/run_guided_learning_simulation.py`
- Test: `tests/test_simulation_runner.py`

**Interfaces:**
- Produces: `build_core_matrix()`, `build_ablation_matrix()`, `run_trajectory(spec)`, and append-only `trajectories.jsonl`/`turns.jsonl`.
- Resume key: `(task_id, persona_id, condition, repeat, freeze_hash)`.

- [ ] **Step 1: Write exact cardinality and resume tests**

```python
def test_matrix_sizes(formal_tasks, personas):
    assert len(build_core_matrix(formal_tasks, personas)) == 216
    assert len(build_ablation_matrix(formal_tasks[:6], personas[:4])) == 72


def test_resume_skips_only_matching_freeze_hash(tmp_path):
    completed = {("T01", "P1", "C0", 1, "hash-a")}
    pending = filter_completed(specs, completed)
    assert all(spec.key != ("T01", "P1", "C0", 1, "hash-a") for spec in pending)
```

- [ ] **Step 2: Implement deterministic matrix construction**

Sort tasks and personas by ID, conditions in C0/C1/C2 or A1/A2/A3 order, and formal repeat `1`. Keep repeats `1,2,3` only as an optional extension. Select the six ablation tasks and four personas from IDs frozen in `freeze_manifest.json`; do not take the first rows implicitly.

- [ ] **Step 3: Implement the turn loop**

Alternate learner generation and condition response until completion, invalidity, technical failure, or eight system turns. Validate learner JSON and the declared state transition against the persona rules, allow one format-only retry, append every turn and state change immediately, and write the trajectory summary only once.

- [ ] **Step 4: Implement CLI gates**

The CLI supports `--mode development|formal`, `--matrix core|ablation|all`, `--max-trajectories`, `--output-dir`, and `--resume`. Formal mode verifies every frozen hash before the first API call and refuses `--max-trajectories` values that would silently relabel a partial run as complete.

- [ ] **Step 5: Run offline runner tests**

Run: `py -m pytest tests/test_simulation_runner.py tests/test_simulation_conditions.py -v`

Expected: all tests pass using fake role clients.

- [ ] **Step 6: Commit runner**

```powershell
git add research_eval/simulation/matrix.py research_eval/simulation/runner.py scripts/run_guided_learning_simulation.py tests/test_simulation_runner.py
git commit -m "feat: run resumable simulation matrix"
```

### Task 6: Rule metrics and leakage review candidates

**Files:**
- Create: `research_eval/simulation/metrics.py`
- Create: `scripts/score_guided_learning_simulation.py`
- Test: `tests/test_simulation_metrics.py`

**Interfaces:**
- Consumes: frozen tasks plus trajectories/turns JSONL.
- Produces: `trajectory_metrics.csv` and `leakage_review_candidates.csv`.

- [ ] **Step 1: Write metric tests with Chinese text and code fences**

Cover complete-code-before-stage detection, reference-step coverage, normalized duplicate hints using `difflib.SequenceMatcher`, stage-order violations, completion, recovery, response counts, and technical failures.

- [ ] **Step 2: Implement conservative metrics**

Mark `possible_complete_code_leakage` only when a pre-permitted response contains a fenced or structurally complete program; mark `possible_full_step_leakage` when normalized text covers all key-step phrases. Keep both as candidates rather than final truth. Compute duplicate hints at similarity `> 0.80`, matching the existing stage-three repetition guard.

- [ ] **Step 3: Emit review candidates with anonymous IDs**

The candidate CSV contains trajectory ID, turn index, rule flags, excerpt, task difficulty, and persona ID. It excludes condition labels from the teacher-facing export generated later.

- [ ] **Step 4: Run tests and commit**

Run: `py -m pytest tests/test_simulation_metrics.py -v`

Expected: all tests pass.

```powershell
git add research_eval/simulation/metrics.py scripts/score_guided_learning_simulation.py tests/test_simulation_metrics.py
git commit -m "feat: score simulation mechanism metrics"
```

### Task 7: Automatic judge, 96-item blind packet, and rating import

**Files:**
- Create: `research_eval/simulation/judging.py`
- Create: `research_eval/simulation/blinding.py`
- Create: `scripts/judge_guided_learning_simulation.py`
- Create: `scripts/build_simulation_teacher_packet.py`
- Create: `scripts/import_simulation_teacher_ratings.py`
- Test: `tests/test_simulation_judging.py`

**Interfaces:**
- Produces: `automatic_ratings.jsonl`, `teacher_packet.xlsx`, `blinding_key.csv`, and validated `teacher_ratings.csv`.
- The packet contains exactly 96 rows and no condition field.

- [ ] **Step 1: Write tests for strict judge JSON and stratified counts**

Test six integer ratings in `[1,5]`, two boolean flags, evidence text for every dimension, rejection of condition labels in judge payloads, exact sample counts 24/24/24/8/8/8, and deterministic sampling from a recorded seed.

- [ ] **Step 2: Implement automatic judging**

Randomize candidate order before constructing the judge message, use the frozen judge prompt and temperature 0.0, append raw judge responses, and validate strict JSON. Invalid output receives one format-only retry; the second failure is retained as a judge technical failure.

- [ ] **Step 3: Implement blinded stratified sampling**

Sample within condition, difficulty, and persona strata using a recorded seed. Generate opaque IDs such as `R0001`; store condition mappings only in `blinding_key.csv`. The workbook contains task text, persona-visible description, transcript, six rating columns, two binary columns, and a comment column.

- [ ] **Step 4: Implement rating import validation**

Require both raters to score every opaque ID, reject out-of-range values, duplicate IDs, missing decisions, and packet IDs absent from the key. Preserve each rater's values separately.

- [ ] **Step 5: Run tests and commit**

Run: `py -m pytest tests/test_simulation_judging.py -v`

Expected: all tests pass without model calls.

```powershell
git add research_eval/simulation/judging.py research_eval/simulation/blinding.py scripts/judge_guided_learning_simulation.py scripts/build_simulation_teacher_packet.py scripts/import_simulation_teacher_ratings.py tests/test_simulation_judging.py
git commit -m "feat: create blinded simulation review workflow"
```

### Task 8: Paired bootstrap, rater agreement, calibration, and figures

**Files:**
- Create: `research_eval/simulation/analysis.py`
- Create: `scripts/analyze_guided_learning_simulation.py`
- Create: `scripts/plot_guided_learning_simulation.py`
- Test: `tests/test_simulation_analysis.py`

**Interfaces:**
- Produces: `core_comparisons.csv`, `ablation_comparisons.csv`, `rater_agreement.csv`, `judge_calibration.csv`, `failure_slices.csv`, and figures.

- [ ] **Step 1: Write statistical tests with fixed toy data**

Test that bootstrap resamples the `(task_id, persona_id)` cluster rather than individual repeats, risk difference equals the hand-calculated value, Holm-adjusted p-values are monotone, weighted Cohen's kappa returns 1.0 for identical ratings, and repeated trajectories never become independent learner counts.

- [ ] **Step 2: Implement paired clustered bootstrap**

Use a fixed recorded NumPy seed and 10,000 resamples. Average repeats within each task-persona-condition cell when the optional extension is run; the formal main experiment has one trajectory per cell. Pivot conditions within the same cell, then resample task-persona cells. Report differences, percentile 95% confidence intervals, standardized paired effects, risk differences, and risk ratios as appropriate.

- [ ] **Step 3: Implement agreement and judge calibration**

Compute weighted Cohen's kappa for ordinal ratings, Cohen's kappa for binary flags, Spearman correlation using average ranks, and mean absolute error between automatic and mean teacher ratings. If agreement is below the threshold recorded in the protocol, label automatic results `supplementary_only=1`.

- [ ] **Step 4: Implement plots without a composite superiority score**

Create separate figures for mechanism metrics by condition, teacher ratings by condition, ablation effects, and difficulty/persona failure slices. Include confidence intervals and measured sample counts. Do not collapse all dimensions into one overall score.

- [ ] **Step 5: Run analysis tests and commit**

Run: `py -m pytest tests/test_simulation_analysis.py -v`

Expected: all tests pass.

```powershell
git add research_eval/simulation/analysis.py scripts/analyze_guided_learning_simulation.py scripts/plot_guided_learning_simulation.py tests/test_simulation_analysis.py
git commit -m "feat: analyze simulation comparisons and agreement"
```

### Task 9: Protocol, dry run, and formal-run approval gates

**Files:**
- Create: `research/guided_learning_paper/simulation_evaluation_protocol.md`
- Modify: `research/guided_learning_paper/README.md`
- Test: `tests/test_simulation_protocol.py`

**Interfaces:**
- Produces: exact development, pilot, formal, judging, packet, and analysis commands.

- [ ] **Step 1: Write protocol-content tests**

Assert that the protocol contains `虚拟学生不是现实学生`, `同一基础模型`, `两位教师`, `96`, `216`, `72`, `288`, `不得调参后保留旧结果`, and all commands below.

- [ ] **Step 2: Write the exact staged commands**

```powershell
py scripts/run_guided_learning_simulation.py --mode development --matrix core --max-trajectories 12 --output-dir research_exports/simulation/development
py scripts/run_guided_learning_simulation.py --mode formal --matrix core --max-trajectories 6 --output-dir research_exports/simulation/formal-smoke
py scripts/run_guided_learning_simulation.py --mode formal --matrix all --output-dir research_exports/simulation/formal --resume
py scripts/score_guided_learning_simulation.py --input research_exports/simulation/formal --output-dir research_exports/simulation/scored
py scripts/judge_guided_learning_simulation.py --input research_exports/simulation/formal --output research_exports/simulation/scored/automatic_ratings.jsonl --resume
py scripts/build_simulation_teacher_packet.py --input research_exports/simulation/formal --ratings research_exports/simulation/scored/trajectory_metrics.csv --output-dir research_exports/simulation/teacher-review --seed 20260721
py scripts/analyze_guided_learning_simulation.py --metrics research_exports/simulation/scored/trajectory_metrics.csv --automatic-ratings research_exports/simulation/scored/automatic_ratings.jsonl --teacher-ratings research_exports/simulation/teacher-review/teacher_ratings.csv --output-dir research/guided_learning_paper/experiments/simulation/results --seed 20260721
```

- [ ] **Step 3: Run the complete offline test suite for the harness**

Run: `py -m pytest tests/test_simulation_*.py -v`

Expected: all tests pass with zero network calls.

- [ ] **Step 4: Run only the 12-trajectory development experiment after external-call approval**

Inspect role isolation, malformed-output rate, state transitions, secret redaction, and JSONL resume behavior. Prompt changes remain allowed at this stage, and all development outputs remain excluded from formal analysis.

- [ ] **Step 5: Freeze configuration and request a second approval for formal smoke**

Recompute hashes, commit the freeze manifest, then run exactly six formal trajectories. Any prompt or schema change after this point invalidates the formal smoke and requires a new freeze commit.

- [ ] **Step 6: Commit protocol and freeze evidence**

```powershell
git add research/guided_learning_paper/simulation_evaluation_protocol.md research/guided_learning_paper/README.md tests/test_simulation_protocol.py research/guided_learning_paper/experiments/simulation/config/freeze_manifest.json
git commit -m "docs: freeze simulation evaluation protocol"
```

### Task 10: Integrate approved aggregate results into the manuscript

**Files:**
- Modify: `research/guided_learning_paper/manuscript_core_zh.md`
- Modify: `research/guided_learning_paper/manuscript_zh.md`
- Modify: `scripts/build_guided_learning_paper_docx.py`
- Test: `tests/test_guided_learning_paper_content.py`
- Test: `tests/test_guided_learning_paper_docx.py`

**Interfaces:**
- Consumes: finalized aggregate CSVs, figures, and teacher-rating agreement.
- Produces: revised Chinese manuscript and rendered Word artifact.

- [ ] **Step 1: Add failing content tests for RQ5-RQ7 and evidence boundaries**

Require the manuscript to name the 216/72 design, 96-item double-teacher review, same-model limitation, paired analysis unit, and explicit statement that simulation does not establish real learning gains.

- [ ] **Step 2: Add methods and results only after final artifacts exist**

Report all predefined conditions, technical failures, confidence intervals, effect sizes, rater agreement, automatic-judge calibration, and unfavorable findings. Do not report development trajectories as formal evidence and do not write numerical values manually when the CSV can generate them.

- [ ] **Step 3: Rebuild and render the Word document**

Run: `py scripts/build_guided_learning_paper_docx.py`

Expected: the document is regenerated from the revised manuscript and includes simulation tables/figures without overlap or clipped captions.

- [ ] **Step 4: Run manuscript and document tests**

Run: `py -m pytest tests/test_guided_learning_paper_content.py tests/test_guided_learning_paper_docx.py -v`

Expected: all tests pass.

- [ ] **Step 5: Commit manuscript integration separately from raw experiments**

```powershell
git add research/guided_learning_paper/manuscript_core_zh.md research/guided_learning_paper/manuscript_zh.md scripts/build_guided_learning_paper_docx.py tests/test_guided_learning_paper_content.py tests/test_guided_learning_paper_docx.py
git commit -m "docs: report guided learning simulation evaluation"
```
