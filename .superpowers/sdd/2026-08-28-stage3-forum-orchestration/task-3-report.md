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
c6c112e
```

## Concerns

1. The brief contains one internal conflict:
   - one bullet says `off_topic` and invalid/empty evidence should consume attempts
   - another bullet says empty/invalid evidence must raise `ValueError` before changing state
   I resolved this by making `off_topic` consume attempts while empty/meaningless evidence raises before any state change.
2. The named verification command in the brief uses `python`, but this workspace currently exposes `py.exe` rather than `python`. I recorded both the failed environment call and the successful equivalent test command above.
