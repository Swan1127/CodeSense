import json
from pathlib import Path
import subprocess
import sys

import pytest

from research_eval.simulation.models import load_personas
from research_eval.simulation.tasks import load_task_manifest
from scripts.run_guided_learning_simulation import (
    build_experiment_specs,
    configuration_paths,
    plan_run,
    verify_frozen_configuration,
)


CONFIG = Path("research/guided_learning_paper/experiments/simulation/config")
PROMPTS = Path("research/guided_learning_paper/experiments/simulation/prompts")


def load_inputs():
    manifest = json.loads((CONFIG / "freeze_manifest.json").read_text(encoding="utf-8"))
    tasks = load_task_manifest(CONFIG / "tasks.json")
    personas = load_personas(CONFIG / "personas.json")
    return manifest, tasks, personas


def test_frozen_configuration_matches_committed_files():
    manifest, _, _ = load_inputs()

    freeze_hash = verify_frozen_configuration(
        manifest,
        configuration_paths(CONFIG, PROMPTS),
    )

    assert len(freeze_hash) == 64


def test_frozen_configuration_rejects_changed_file(tmp_path):
    manifest, _, _ = load_inputs()
    paths = configuration_paths(CONFIG, PROMPTS)
    changed = tmp_path / "learner.txt"
    changed.write_text("changed", encoding="utf-8")
    paths["prompt_learner"] = changed

    with pytest.raises(ValueError, match="prompt_learner"):
        verify_frozen_configuration(manifest, paths)


def test_formal_specs_have_exact_core_and_ablation_cardinality():
    manifest, tasks, personas = load_inputs()

    core = build_experiment_specs(
        "formal", "core", tasks, personas, manifest, "freeze-a"
    )
    ablation = build_experiment_specs(
        "formal", "ablation", tasks, personas, manifest, "freeze-a"
    )
    all_specs = build_experiment_specs(
        "formal", "all", tasks, personas, manifest, "freeze-a"
    )

    assert len(core) == 216
    assert len(ablation) == 72
    assert len(all_specs) == 288
    assert {row.repeat for row in all_specs} == {1}


def test_development_specs_exclude_formal_tasks_and_use_one_repeat():
    manifest, tasks, personas = load_inputs()

    specs = build_experiment_specs(
        "development", "core", tasks, personas, manifest, "dev-hash"
    )

    assert len(specs) == 36
    assert {row.task_id for row in specs} == set(manifest["development_task_ids"])
    assert {row.repeat for row in specs} == {1}


def test_limited_run_is_explicitly_partial():
    manifest, tasks, personas = load_inputs()
    specs = build_experiment_specs(
        "formal", "core", tasks, personas, manifest, "freeze-a"
    )

    selected, status = plan_run(specs, 6)

    assert len(selected) == 6


def test_script_entrypoint_can_load_repository_modules():
    result = subprocess.run(
        [sys.executable, "scripts/run_guided_learning_simulation.py", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--mode" in result.stdout


def test_cli_reconfigures_gbk_streams_to_utf8():
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "gbk"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from scripts.run_guided_learning_simulation import "
                "configure_utf8_stdio; "
                "configure_utf8_stdio(); print(\"✅ 编码检查\")"
            ),
        ],
        capture_output=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode("gbk", errors="replace")
    assert "编码检查" in result.stdout.decode("utf-8")
