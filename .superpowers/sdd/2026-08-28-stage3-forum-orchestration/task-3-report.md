# Task 3 Report: Stage 3 Concept Coverage Gate

Date: 2026-08-28
Branch: current working branch
Task brief: `.superpowers/sdd/2026-08-28-stage3-forum-orchestration/task-3-brief.md`

## Changed Files

- `utils/agents/coverage.py`
- `tests/test_stage3_coverage.py`

No routes, tools, loop, templates, or memory files were modified in this task.

## Context Reviewed Before Editing

- `utils/agents/contracts.py`
- `utils/agents/feynman.py`
- `utils/agents/tools.py`
- `utils/agents/memory.py`
- `tests/test_stage3_forum_contracts.py`
- `tests/test_stage3_agent_tools.py`
- `docs/superpowers/specs/2026-08-28-stage3-forum-orchestration-design.md`
- `docs/superpowers/plans/2026-08-28-stage3-forum-agent-orchestration.md`

## Red Phase

I first tried the command named in the brief:

Command:

```powershell
python -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
python:
Line |
   2 |  python -m pytest tests/test_stage3_coverage.py -q
     |  ~~~~~~
     | The term 'python' is not recognized as a name of a cmdlet, function, script file, or executable program.
Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
```

After confirming the environment exposes `py.exe`, I reran the same test target through the available interpreter to complete the required red phase:

Command:

```powershell
py -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
=================================== ERRORS ====================================
_______________ ERROR collecting tests/test_stage3_coverage.py ________________
ImportError while importing test module 'E:\CodeSense\stage3-forum-agent-interaction\tests\test_stage3_coverage.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
E:\anaconda\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\test_stage3_coverage.py:4: in <module>
    from utils.agents.coverage import (
E   ModuleNotFoundError: No module named 'utils.agents.coverage'
=========================== short test summary info ===========================
ERROR tests/test_stage3_coverage.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.25s
```

This was the expected failure: the new reducer module did not exist yet.

## Green Phase

Command:

```powershell
py -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
.......                                                                  [100%]
7 passed in 0.12s
```

## Required Verification

Command:

```powershell
git diff --check
```

Output:

```text
<no output>
```

## Design Decisions

1. `concept_coverage` is stored as an ordered JSON-serializable list of per-concept dictionaries, not a map. This matches the existing `FeynmanState` field shape better, preserves deterministic ordering from `key_concepts`, and stays easy to merge into a state snapshot.
2. Each concept entry keeps:
   - `concept`
   - `status`
   - `attempts`
   - `used_dimensions`
   - `attempt_event_ids`
   - `accepted_evidence_count`
   - `evidence_event_ids`
   - `last_evidence_event_id`
3. Coverage scoring is deterministic and bounded:
   - `covered` contributes full weight
   - `partial` contributes half weight
   - `off_topic` and `unseen` contribute zero
   - default weight is equal per concept unless a future state entry supplies a positive `weight`
4. The reducer is pure and does not mutate the incoming `FeynmanState`. It normalizes old or missing coverage state, computes the next probe, and returns a minimal `state_patch`.
5. `ready_for_code` is gated by both conditions from the brief:
   - `coverage_score >= min_coverage`
   - `pending_probe is None`

## Self-Review

- Public interfaces match the brief exactly: `CoverageConfig`, `CoverageDecision`, `load_coverage_config`, `apply_coverage_assessment`.
- The implementation reads legacy state safely and does not depend on loop, route, tool, or memory changes.
- Tests cover:
  - legacy config fallback
  - immediate concept completion on `covered`
  - dimension uniqueness and max-probe enforcement
  - `off_topic` consuming an attempt without creating false mastery
  - empty evidence rejection before state changes
  - ready-for-code gating
  - deterministic equal-weight scoring boundaries
- The reducer currently treats `partial` as half credit. That is intentional and documented in the test suite so later task integration cannot silently change the rule.

## Commit

Commit message required by brief:

```text
feat: add stage3 concept coverage gate
```

Commit SHA:

```text
d032c46
```

## Concerns

1. The brief contains one internal conflict:
   - one bullet says `off_topic` and invalid/empty evidence should consume attempts
   - another bullet says empty/invalid evidence must raise `ValueError` before changing state
   I resolved this by making `off_topic` consume attempts while empty/meaningless evidence raises before any state change.
2. The named verification command in the brief uses `python`, but this workspace currently exposes `py.exe` rather than `python`. I recorded both the failed environment call and the successful equivalent test command above.

## Fix Round 1

### Reviewer Findings Addressed

1. `covered` and `partial` assessments now require conservative server-side concrete evidence validation. Generic acknowledgements, filler, and non-explanatory text are rejected with `ValueError` before any state change.
2. `load_coverage_config()` now rejects configs where `len(probe_dimensions) < max_probes_per_concept`.

### Changed Files

- `utils/agents/coverage.py`
- `tests/test_stage3_coverage.py`
- `.superpowers/sdd/2026-08-28-stage3-forum-orchestration/task-3-report.md`

### Red Phase

Command:

```powershell
py -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
.F....FFFFFFFFFFFF...                                                    [100%]
================================== FAILURES ===================================
____ test_load_coverage_config_rejects_more_probes_than_unique_dimensions _____

    def test_load_coverage_config_rejects_more_probes_than_unique_dimensions():
>       with pytest.raises(ValueError, match="probe_dimensions"):
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:23: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u597d\u7684\uff0c\u6211\u61c2\u4e86] _

text = '�õģ��Ҷ���'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u55ef\u55ef] _

text = '����'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[yes] _

text = 'yes'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[ok thanks] _

text = 'ok thanks'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u6536\u5230] _

text = '�յ�'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[I understand] _

text = 'I understand'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u660e\u767d\u4e86\uff0c\u8c22\u8c22\u8001\u5e08] _

text = '�����ˣ�лл��ʦ'

    @pytest.mark.parametrize("text", [
        "�õģ��Ҷ���",
        "����",
        "yes",
        "ok thanks",
        "�յ�",
        "I understand",
        "�����ˣ�лл��ʦ",
    ])
    def test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:198: Failed
_ test_non_explanatory_statements_cannot_mark_concept_as_covered[\u8fd9\u4e2a\u77e5\u8bc6\u70b9\u5f88\u91cd\u8981\u3002] _

text = '���֪ʶ�����Ҫ��'

    @pytest.mark.parametrize("text", [
        "���֪ʶ�����Ҫ��",
        "����Ŀ�йء�",
        "It makes sense now.",
        "����һ��ˡ�",
        "��Ҫע��ϸ�ڡ�",
    ])
    def test_non_explanatory_statements_cannot_mark_concept_as_covered(text):
        state = FeynmanState(session_id=12)

>       with pytest.raises(ValueError, match="concrete evidence"):
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:221: Failed
_ test_non_explanatory_statements_cannot_mark_concept_as_covered[\u8ddf\u9898\u76ee\u6709\u5173\u3002] _

text = '����Ŀ�йء�'

    @pytest.mark.parametrize("text", [
        "���֪ʶ�����Ҫ��",
        "����Ŀ�йء�",
        "It makes sense now.",
        "����һ��ˡ�",
        "��Ҫע��ϸ�ڡ�",
    ])
    def test_non_explanatory_statements_cannot_mark_concept_as_covered(text):
        state = FeynmanState(session_id=12)

>       with pytest.raises(ValueError, match="concrete evidence"):
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:221: Failed
_ test_non_explanatory_statements_cannot_mark_concept_as_covered[It makes sense now.] _

text = 'It makes sense now.'

    @pytest.mark.parametrize("text", [
        "���֪ʶ�����Ҫ��",
        "����Ŀ�йء�",
        "It makes sense now.",
        "����һ��ˡ�",
        "��Ҫע��ϸ�ڡ�",
    ])
    def test_non_explanatory_statements_cannot_mark_concept_as_covered(text):
        state = FeynmanState(session_id=12)

>       with pytest.raises(ValueError, match="concrete evidence"):
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:221: Failed
_ test_non_explanatory_statements_cannot_mark_concept_as_covered[\u8fd9\u4e2a\u6211\u4f1a\u4e86\u3002] _

text = '����һ��ˡ�'

    @pytest.mark.parametrize("text", [
        "���֪ʶ�����Ҫ��",
        "����Ŀ�йء�",
        "It makes sense now.",
        "����һ��ˡ�",
        "��Ҫע��ϸ�ڡ�",
    ])
    def test_non_explanatory_statements_cannot_mark_concept_as_covered(text):
        state = FeynmanState(session_id=12)

>       with pytest.raises(ValueError, match="concrete evidence"):
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:221: Failed
_ test_non_explanatory_statements_cannot_mark_concept_as_covered[\u9700\u8981\u6ce8\u610f\u7ec6\u8282\u3002] _

text = '��Ҫע��ϸ�ڡ�'

    @pytest.mark.parametrize("text", [
        "���֪ʶ�����Ҫ��",
        "����Ŀ�йء�",
        "It makes sense now.",
        "����һ��ˡ�",
        "��Ҫע��ϸ�ڡ�",
    ])
    def test_non_explanatory_statements_cannot_mark_concept_as_covered(text):
        state = FeynmanState(session_id=12)

>       with pytest.raises(ValueError, match="concrete evidence"):
E       Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:221: Failed
=========================== short test summary info ===========================
FAILED tests/test_stage3_coverage.py::test_load_coverage_config_rejects_more_probes_than_unique_dimensions
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u597d\u7684\uff0c\u6211\u61c2\u4e86]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u55ef\u55ef]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[yes]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[ok thanks]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u6536\u5230]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[I understand]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_acknowledgements_cannot_create_covered_or_partial_evidence[\u660e\u767d\u4e86\uff0c\u8c22\u8c22\u8001\u5e08]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_statements_cannot_mark_concept_as_covered[\u8fd9\u4e2a\u77e5\u8bc6\u70b9\u5f88\u91cd\u8981\u3002]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_statements_cannot_mark_concept_as_covered[\u8ddf\u9898\u76ee\u6709\u5173\u3002]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_statements_cannot_mark_concept_as_covered[It makes sense now.]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_statements_cannot_mark_concept_as_covered[\u8fd9\u4e2a\u6211\u4f1a\u4e86\u3002]
FAILED tests/test_stage3_coverage.py::test_non_explanatory_statements_cannot_mark_concept_as_covered[\u9700\u8981\u6ce8\u610f\u7ec6\u8282\u3002]
13 failed, 8 passed in 0.27s
```

### Green Phase

Command:

```powershell
py -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
.....................                                                    [100%]
21 passed in 0.10s
```

### Verification

Command:

```powershell
git diff --check
```

Output:

```text
<no output>
```

### Fix Round 1 Commit SHA

```text
f3acfd0
```

## Fix Round 2

### Reviewer Findings Addressed

1. Replaced the marker-only concrete-evidence check with a conservative structural validator that rejects isolated markers, digits, symbols, and acknowledgement-plus-marker filler.
2. Added positive regressions for valid paraphrases that do not rely on the previous marker vocabulary, while preserving prior covered/partial scoring semantics and the 3-probe/2-dimension config rejection.

### Changed Files

- `utils/agents/coverage.py`
- `tests/test_stage3_coverage.py`
- `.superpowers/sdd/2026-08-28-stage3-forum-orchestration/task-3-report.md`

### Red Phase

Command:

```powershell
py -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
..................FFF.FFF.....                                           [100%]
================================== FAILURES ===================================
_ test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[if] _

text = 'if'

    @pytest.mark.parametrize("text", [
        "if",
        "because",
        "1",
        "=",
        "ok because",
        "лл����Ϊ",
        "I understand if",
    ])
    def test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:247: Failed
_ test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[because] _

text = 'because'

    @pytest.mark.parametrize("text", [
        "if",
        "because",
        "1",
        "=",
        "ok because",
        "лл����Ϊ",
        "I understand if",
    ])
    def test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:247: Failed
_ test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[1] _

text = '1'

    @pytest.mark.parametrize("text", [
        "if",
        "because",
        "1",
        "=",
        "ok because",
        "лл����Ϊ",
        "I understand if",
    ])
    def test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:247: Failed
_ test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[ok because] _

text = 'ok because'

    @pytest.mark.parametrize("text", [
        "if",
        "because",
        "1",
        "=",
        "ok because",
        "лл����Ϊ",
        "I understand if",
    ])
    def test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:247: Failed
_ test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[\u8c22\u8c22\uff0c\u56e0\u4e3a] _

text = 'лл����Ϊ'

    @pytest.mark.parametrize("text", [
        "if",
        "because",
        "1",
        "=",
        "ok because",
        "лл����Ϊ",
        "I understand if",
    ])
    def test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:247: Failed
_ test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[I understand if] _

text = 'I understand if'

    @pytest.mark.parametrize("text", [
        "if",
        "because",
        "1",
        "=",
        "ok because",
        "лл����Ϊ",
        "I understand if",
    ])
    def test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence(text):
        state = FeynmanState(session_id=12)

        for assessment in ("covered", "partial"):
>           with pytest.raises(ValueError, match="concrete evidence"):
E           Failed: DID NOT RAISE <class 'ValueError'>

tests\test_stage3_coverage.py:247: Failed
=========================== short test summary info ===========================
FAILED tests/test_stage3_coverage.py::test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[if]
FAILED tests/test_stage3_coverage.py::test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[because]
FAILED tests/test_stage3_coverage.py::test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[1]
FAILED tests/test_stage3_coverage.py::test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[ok because]
FAILED tests/test_stage3_coverage.py::test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[\u8c22\u8c22\uff0c\u56e0\u4e3a]
FAILED tests/test_stage3_coverage.py::test_marker_only_digit_only_and_ack_with_marker_are_not_concrete_evidence[I understand if]
6 failed, 24 passed in 0.22s
```

### Green Phase

Command:

```powershell
py -m pytest tests/test_stage3_coverage.py -q
```

Output:

```text
..............................                                           [100%]
30 passed in 0.11s
```

### Verification

Command:

```powershell
git diff --check
```

Output:

```text
<no output>
```

### Fix Round 2 Commit SHA

```text
PENDING
```
