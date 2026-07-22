from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

from dotenv import load_dotenv

from research_eval.simulation.conditions import StructuralAdapter
from research_eval.simulation.framework_adapter import FrameworkAdapter
from research_eval.simulation.matrix import (
    TrajectorySpec,
    build_ablation_matrix,
    build_core_matrix,
    filter_completed,
)
from research_eval.simulation.models import Condition, Persona, TaskCase, content_sha256, load_personas
from research_eval.simulation.runner import JsonlSink, load_finalized_keys, run_trajectory
from research_eval.simulation.tasks import load_task_manifest
from research_eval.simulation.zhipu_roles import RoleClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = PROJECT_ROOT / "research/guided_learning_paper/experiments/simulation/config"
PROMPT_ROOT = PROJECT_ROOT / "research/guided_learning_paper/experiments/simulation/prompts"


def configuration_paths(config_root: Path, prompt_root: Path) -> dict[str, Path]:
    return {
        "tasks": config_root / "tasks.json",
        "personas": config_root / "personas.json",
        "prompt_learner": prompt_root / "learner.txt",
        "prompt_direct_answer": prompt_root / "direct_answer.txt",
        "prompt_fixed_three_stage": prompt_root / "fixed_three_stage.txt",
        "prompt_judge": prompt_root / "judge.txt",
    }


def verify_frozen_configuration(
    manifest: Mapping[str, object],
    paths: Mapping[str, Path],
) -> str:
    frozen = manifest.get("frozen_files")
    if not isinstance(frozen, dict):
        raise ValueError("freeze manifest has no frozen_files object")
    for name, path in sorted(paths.items()):
        expected = str(frozen.get(name, ""))
        actual = content_sha256(path)
        if not expected or actual != expected:
            raise ValueError(f"frozen configuration mismatch: {name}")
    return _freeze_hash(manifest)


def current_configuration_hash(
    manifest: Mapping[str, object],
    paths: Mapping[str, Path],
) -> str:
    payload = {
        "files": {name: content_sha256(path) for name, path in sorted(paths.items())},
        "model": manifest.get("model"),
        "role_parameters": manifest.get("role_parameters"),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_experiment_specs(
    mode: str,
    matrix: str,
    tasks: Sequence[TaskCase],
    personas: Sequence[Persona],
    manifest: Mapping[str, object],
    freeze_hash: str,
) -> list[TrajectorySpec]:
    if mode == "development":
        if matrix != "core":
            raise ValueError("development mode supports only the core matrix")
        development_ids = {str(item) for item in manifest["development_task_ids"]}
        development_tasks = sorted(
            (task for task in tasks if task.task_id in development_ids),
            key=lambda row: row.task_id,
        )
        ordered_personas = sorted(personas, key=lambda row: row.persona_id)
        return [
            TrajectorySpec(
                task.task_id,
                persona.persona_id,
                condition.value,
                1,
                freeze_hash,
            )
            for task in development_tasks
            for persona in ordered_personas
            for condition in (Condition.C0, Condition.C1, Condition.C2)
        ]

    if mode != "formal":
        raise ValueError(f"unsupported mode: {mode}")
    core = build_core_matrix(tasks, personas, freeze_hash)
    ablation = build_ablation_matrix(
        tasks,
        personas,
        freeze_hash,
        [str(item) for item in manifest["ablation_task_ids"]],
        [str(item) for item in manifest["ablation_persona_ids"]],
    )
    if matrix == "core":
        return core
    if matrix == "ablation":
        return ablation
    if matrix == "all":
        return core + ablation
    raise ValueError(f"unsupported matrix: {matrix}")


def plan_run(
    specs: Sequence[TrajectorySpec],
    max_trajectories: int | None,
) -> tuple[list[TrajectorySpec], str]:
    if max_trajectories is not None and max_trajectories <= 0:
        raise ValueError("max_trajectories must be positive")
    selected = list(specs if max_trajectories is None else specs[:max_trajectories])
    scope = "complete" if len(selected) == len(specs) else "partial"
    return selected, scope


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the guided-learning simulation serially")
    parser.add_argument("--mode", choices=("development", "formal"), required=True)
    parser.add_argument("--matrix", choices=("core", "ablation", "all"), required=True)
    parser.add_argument("--max-trajectories", type=int)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--env-file", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    else:
        load_dotenv(PROJECT_ROOT / ".env", override=False)

    api_key = os.environ.get("ZHIPU_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("ZHIPU_API_KEY is missing; pass --env-file or set the environment")

    manifest = json.loads(
        (CONFIG_ROOT / "freeze_manifest.json").read_text(encoding="utf-8")
    )
    paths = configuration_paths(CONFIG_ROOT, PROMPT_ROOT)
    if args.mode == "formal":
        freeze_hash = verify_frozen_configuration(manifest, paths)
    else:
        freeze_hash = current_configuration_hash(manifest, paths)

    tasks = load_task_manifest(paths["tasks"])
    personas = load_personas(paths["personas"])
    all_specs = build_experiment_specs(
        args.mode, args.matrix, tasks, personas, manifest, freeze_hash
    )

    output_dir = args.output_dir.resolve()
    trajectory_path = output_dir / "trajectories.jsonl"
    turn_path = output_dir / "turns.jsonl"
    if trajectory_path.exists() and trajectory_path.stat().st_size and not args.resume:
        raise SystemExit("output already contains trajectories; use --resume")
    pending = filter_completed(all_specs, load_finalized_keys(trajectory_path))
    selected, planned_scope = plan_run(pending, args.max_trajectories)

    prompts = {
        name: path.read_text(encoding="utf-8")
        for name, path in paths.items()
        if name.startswith("prompt_")
    }
    prompt_hashes = {
        name.removeprefix("prompt_"): content_sha256(path)
        for name, path in paths.items()
        if name.startswith("prompt_")
    }
    run_manifest_path = output_dir / "run_manifest.json"
    run_manifest = {
        "mode": args.mode,
        "matrix": args.matrix,
        "freeze_hash": freeze_hash,
        "matrix_size": len(all_specs),
        "already_finalized": len(all_specs) - len(pending),
        "planned_this_invocation": len(selected),
        "planned_scope": planned_scope,
        "execution_status": "running",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "finished_at_utc": "",
    }
    _write_json(run_manifest_path, run_manifest)

    learner_client = RoleClient(api_key)
    system_client = RoleClient(api_key)
    task_map = {row.task_id: row for row in tasks}
    persona_map = {row.persona_id: row for row in personas}
    turn_sink = JsonlSink(turn_path)
    trajectory_sink = JsonlSink(trajectory_path)

    try:
        for index, spec in enumerate(selected, 1):
            adapter = _make_adapter(
                spec.condition,
                system_client,
                prompts["prompt_direct_answer"],
                prompts["prompt_fixed_three_stage"],
            )
            trajectory = run_trajectory(
                spec,
                task_map[spec.task_id],
                persona_map[spec.persona_id],
                learner_client,
                adapter,
                prompts["prompt_learner"],
                prompt_hashes,
                turn_sink,
                trajectory_sink,
            )
            print(
                f"[{index}/{len(selected)}] {trajectory.trajectory_id} "
                f"completed={trajectory.completed} invalid={trajectory.invalid_reason or '-'}",
                flush=True,
            )
    finally:
        run_manifest["execution_status"] = "finished"
        run_manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        run_manifest["finalized_after_run"] = len(load_finalized_keys(trajectory_path))
        _write_json(run_manifest_path, run_manifest)
    return 0


def _make_adapter(
    condition_value: str,
    system_client: RoleClient,
    direct_prompt: str,
    fixed_prompt: str,
):
    condition = Condition(condition_value)
    if condition in {Condition.C0, Condition.C1}:
        return StructuralAdapter(condition, system_client, direct_prompt, fixed_prompt)
    return FrameworkAdapter(condition)


def _freeze_hash(manifest: Mapping[str, object]) -> str:
    payload = {
        "frozen_files": manifest.get("frozen_files"),
        "model": manifest.get("model"),
        "role_parameters": manifest.get("role_parameters"),
        "ablation_task_ids": manifest.get("ablation_task_ids"),
        "ablation_persona_ids": manifest.get("ablation_persona_ids"),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


