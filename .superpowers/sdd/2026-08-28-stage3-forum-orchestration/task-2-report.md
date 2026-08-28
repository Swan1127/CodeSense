# Task 2 report

## Changed files

- `tests/test_stage3_forum_memory.py`
- `utils/agents/memory.py`

## What changed

Task 2 adds a public forum timeline projection and a stricter Student Agent memory projection.

- `MemoryStore.forum_events(session_id)` now returns a public event list instead of raw event records.
- The memory layer now reads `target_role`, `message_kind`, `source_role`, and `visibility` from event metadata.
- Student Agent context now admits only:
  - Student-target user messages
  - Student Agent's own public replies and probes
- Legacy `chat` records still recover their target from `metadata.panel`.
- Teacher replies, tool traffic, and hidden artifacts remain outside the Student Agent prompt surface.

## Red phase

Command:

```powershell
py -m pytest tests/test_stage3_forum_memory.py -q
```

Output:

```text
FFF.                                                                     [100%]
================================== FAILURES ===================================
___________ test_forum_events_project_only_public_timeline_messages ___________

E       AttributeError: 'MemoryStore' object has no attribute 'forum_events'

_ test_student_view_only_includes_student_target_messages_and_student_agent_replies _

E       AssertionError: assert [...] == [...]

__________ test_forum_events_infer_legacy_target_from_panel_metadata __________

E       AttributeError: 'MemoryStore' object has no attribute 'forum_events'

=========================== short test summary info ============================
FAILED tests/test_stage3_forum_memory.py::test_forum_events_project_only_public_timeline_messages
FAILED tests/test_stage3_forum_memory.py::test_student_view_only_includes_student_target_messages_and_student_agent_replies
FAILED tests/test_stage3_forum_memory.py::test_forum_events_infer_legacy_target_from_panel_metadata
3 failed, 1 passed in 0.18s
```

## Green phase

Targeted command:

```powershell
py -m pytest tests/test_stage3_forum_memory.py -q
```

Output:

```text
....                                                                     [100%]
4 passed in 0.10s
```

Required regression command:

```powershell
py -m pytest tests/test_stage3_forum_memory.py tests/test_stage3_agent_memory.py tests/test_stage3_agent_loop.py -q
```

Output:

```text
..........................................................               [100%]
============================== warnings summary ===============================
tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception
tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception
  E:\anaconda\Lib\site-packages\werkzeug\routing\rules.py:751: DeprecationWarning: ast.Str is deprecated and will be removed in Python 3.14; use ast.Constant instead
    parts = parts or [ast.Str("")]

tests/test_stage3_agent_loop.py: 12 warnings
  E:\anaconda\Lib\site-packages\werkzeug\routing\rules.py:748: DeprecationWarning: ast.Str is deprecated and will be removed in Python 3.14; use ast.Constant instead
    _convert(elem) if is_dynamic else ast.Str(s=elem)

tests/test_stage3_agent_loop.py: 12 warnings
  E:\anaconda\Lib\ast.py:602: DeprecationWarning: Constant.__init__ got an unexpected keyword argument 's'. Support for arbitrary keyword arguments is deprecated and will be removed in Python 3.15.
    return Constant(*args, **kwargs)

tests/test_stage3_agent_loop.py: 12 warnings
  E:\anaconda\Lib\ast.py:602: DeprecationWarning: Attribute s is deprecated and will be removed in Python 3.14; use value instead
    return Constant(*args, **kwargs)

tests/test_stage3_agent_loop.py: 12 warnings
  E:\anaconda\Lib\ast.py:602: DeprecationWarning: Constant.__init__ missing 1 required positional argument: 'value'. This will become an error in Python 3.15.
    return Constant(*args, **kwargs)

tests/test_stage3_agent_loop.py: 20 warnings
  E:\anaconda\Lib\site-packages\werkzeug\routing\rules.py:755: DeprecationWarning: ast.Str is deprecated and will be removed in Python 3.14; use ast.Constant instead
    if isinstance(p, ast.Str) and isinstance(ret[-1], ast.Str):

tests/test_stage3_agent_loop.py: 16 warnings
  E:\anaconda\Lib\site-packages\werkzeug\routing\rules.py:756: DeprecationWarning: Attribute s is deprecated and will be removed in Python 3.14; use value instead
    ret[-1] = ast.Str(ret[-1].s + p.s)

tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_agent_loop_uses_configured_redis_lock_with_ttl
tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception
tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception
tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception
tests/test_stage3_agent_loop.py::test_redis_lock_releases_and_preserves_body_exception
  E:\anaconda\Lib\site-packages\werkzeug\routing\rules.py:756: DeprecationWarning: ast.Str is deprecated and will be removed in Python 3.14; use ast.Constant instead
    ret[-1] = ast.Str(ret[-1].s + p.s)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
58 passed, 97 warnings in 0.62s
```

Formatting check:

```powershell
git diff --check
```

Output:

```text
[no output]
```

## Self-review notes

- The Student Agent filter is metadata-driven. It does not inspect message text.
- Existing memory behavior for old untagged `agent_user_message` records remains intact by falling back to prior visibility.
- Legacy `chat` records with `metadata.panel` still project into the public forum view.
- I did not change routes, templates, tools, or loop code.
- The implementation is intentionally narrow. It adds just enough metadata inference to satisfy Task 2 without expanding serialization or persistence interfaces beyond this layer.

## Commit

- Implementation commit: `cb06d59075ae80cacf2ace50df7ddbd00000e3a7` (`feat: project stage3 memory by forum target`)
- Report commit: `6f285e2` (`docs: add task 2 implementation report`)

## Concerns

- The shell in this workspace does not expose `python` on `PATH`; I had to use `py -m pytest`.
- The required regression suite passes, but it still emits 97 pre-existing Werkzeug deprecation warnings under the current interpreter.
