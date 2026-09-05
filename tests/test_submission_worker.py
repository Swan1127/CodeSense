import inspect
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask

try:
    import tasks.submission_tasks as worker_tasks
    from tasks.submission_tasks import (
        run_formal_submission_evaluation,
        run_submission_evaluation,
    )
    import tasks.submission_worker as worker_module
    _IMPORT_ERROR = None
except ImportError as exc:  # Keep the RED phase as an assertion failure.
    worker_tasks = None
    run_formal_submission_evaluation = None
    run_submission_evaluation = None
    worker_module = None
    _IMPORT_ERROR = str(exc)


def _require_worker_contract():
    assert worker_module is not None and run_formal_submission_evaluation is not None, (
        "submission worker contract is not available: " + str(_IMPORT_ERROR)
    )


def test_formal_worker_resolves_assignment_from_opaque_submission_id():
    _require_worker_contract()
    app = Flask(__name__)
    submission = SimpleNamespace(assignment_id=9, student_id="student-private")
    assignment = SimpleNamespace(title="循环题")
    fake_submission_model = object()
    fake_assignment_model = object()

    def get(model, value):
        if model is fake_submission_model:
            assert value == 17
            return submission
        if model is fake_assignment_model:
            assert value == 9
            return assignment
        raise AssertionError("unexpected model lookup")

    fake_db = SimpleNamespace(session=SimpleNamespace(get=get))
    with app.app_context(), \
            patch.object(worker_tasks, "db", fake_db), \
            patch.object(worker_tasks, "Submission", fake_submission_model), \
            patch.object(worker_tasks, "Assignment", fake_assignment_model), \
            patch.object(
                worker_tasks, "run_submission_evaluation", return_value="evaluated"
            ) as run:
        assert run_formal_submission_evaluation(17) == "evaluated"

    run.assert_called_once_with(app, 17, "循环题", None)
    assert list(inspect.signature(run_formal_submission_evaluation).parameters) == [
        "submission_id"
    ]


def test_worker_entry_disables_web_threads_and_preset_scanner(monkeypatch):
    _require_worker_contract()
    app = Flask(__name__)
    app.config["SUBMISSION_EVALUATION_QUEUE_BACKEND"] = "rq"
    fake_app_module = ModuleType("app")
    fake_app_module.app = app
    fake_worker = SimpleNamespace(work=lambda **kwargs: True)
    monkeypatch.setenv("CODESENSE_CONFIG", "testing")
    monkeypatch.setenv("ASYNC_TASKS_ENABLED", "1")
    monkeypatch.setenv("PRESET_SCAN_ENABLED", "1")
    monkeypatch.setenv("ACCESS_LOG_ENABLED", "1")
    with patch.dict(sys.modules, {"app": fake_app_module}), \
            patch.object(
                worker_module, "build_worker", return_value=fake_worker
            ) as build:
        assert worker_module.main() == 0

    assert worker_module.os.environ["FLASK_CONFIG"] == "testing"
    assert worker_module.os.environ["ASYNC_TASKS_ENABLED"] == "0"
    assert worker_module.os.environ["PRESET_SCAN_ENABLED"] == "0"
    assert worker_module.os.environ["ACCESS_LOG_ENABLED"] == "0"
    build.assert_called_once_with(app)

