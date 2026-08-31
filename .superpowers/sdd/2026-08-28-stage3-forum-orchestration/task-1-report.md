# Task 1 Report

## Changed files

- `tests/test_stage3_forum_contracts.py`
- `utils/agents/contracts.py`
- `utils/agents/__init__.py`

## Test commands and outputs

### Red phase

Command:

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_forum_contracts.py tests/test_stage3_agent_memory.py -q
```

Output:

```text
=================================== ERRORS ====================================
____________ ERROR collecting tests/test_stage3_forum_contracts.py ____________
ImportError while importing test module 'E:\CodeSense\stage3-forum-agent-interaction\tests\test_stage3_forum_contracts.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
E:\anaconda\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\test_stage3_forum_contracts.py:1: in <module>
    from utils.agents.contracts import (
E   ImportError: cannot import name 'ForumEnvelope' from 'utils.agents.contracts' (E:\CodeSense\stage3-forum-agent-interaction\utils\agents\contracts.py)
=========================== short test summary info ============================
ERROR tests/test_stage3_forum_contracts.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.34s
```

### Green phase

Command:

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_forum_contracts.py tests/test_stage3_agent_memory.py -q
```

Output:

```text
....................                                                     [100%]
20 passed in 0.11s
```

### Diff check

Command:

```powershell
git -C 'E:/CodeSense/stage3-forum-agent-interaction' diff --check
```

Output:

```text
[no output]
```

## Self-review notes

- Added `Stage3Target` and `Stage3MessageKind` as stable string enums for public routing contracts.
- Added `ForumEnvelope.to_metadata()` with the exact metadata keys required by the task brief.
- Extended `FeynmanState` with the new forum defaults while preserving compatibility fields such as `feynman_rounds` and `key_concepts`.
- Added `internal_signals` to `AgentResult` and kept it out of `to_public_dict()`.
- Re-exported the new public contract types from `utils.agents.__init__`.

## Commit SHA

- `0688505`

## Concerns

- None at completion.

## Fix round 1

### Finding

- Critical: `AgentResult.to_public_dict()` merged `public_content` directly, so a reserved internal key such as `internal_signals` could leak orchestration-only data.

### Changed lines

- `tests/test_stage3_forum_contracts.py`: expanded `test_agent_result_to_public_dict_filters_internal_signals()` to include `public_content={"internal_signals": {"secret": True}}` and assert the key is removed while normal public content remains visible.
- `utils/agents/contracts.py:11`: added `_INTERNAL_PUBLIC_CONTENT_KEYS = frozenset({"internal_signals"})`.
- `utils/agents/contracts.py:206-219`: filtered reserved keys out of `public_content` before merging into the public payload.

### Commands and exact outputs

#### Red phase

Command:

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_forum_contracts.py tests/test_stage3_agent_memory.py -q
```

Output:

```text
....F...............                                                     [100%]
================================== FAILURES ===================================
__________ test_agent_result_to_public_dict_filters_internal_signals __________

    def test_agent_result_to_public_dict_filters_internal_signals():
        result = AgentResult(
            success=True,
            agent=Stage3Target.STUDENT_AGENT,
            response="������",
            state={"phase": "student_dialogue"},
            public_content={
                "message": "visible",
                "internal_signals": {"secret": True},
            },
            internal_signals={"next_actor": "teacher_agent"},
        )

        public = result.to_public_dict()

        assert public["message"] == "visible"
>       assert "internal_signals" not in public
E       AssertionError: assert 'internal_signals' not in {'agent': 'student_agent', 'internal_signals': {'secret': True}, 'message': 'visible', 'ready_for_code': False, ...}

tests\test_stage3_forum_contracts.py:77: AssertionError
=========================== short test summary info ============================
FAILED tests/test_stage3_forum_contracts.py::test_agent_result_to_public_dict_filters_internal_signals
1 failed, 19 passed in 0.20s
```

#### Green phase

Command:

```powershell
& 'E:\anaconda\python.exe' -m pytest tests/test_stage3_forum_contracts.py tests/test_stage3_agent_memory.py -q
```

Output:

```text
....................                                                     [100%]
20 passed in 0.09s
```

#### Diff check

Command:

```powershell
git -C 'E:/CodeSense/stage3-forum-agent-interaction' diff --check
```

Output:

```text
[no output]
```
