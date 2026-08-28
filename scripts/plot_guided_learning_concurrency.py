"""Regenerate paper figures from an existing concurrency summary."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from research_eval.concurrency.cli import load_summary_rows, plot_summary_rows  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    output_dir = args.output_dir.resolve()
    rows = load_summary_rows(output_dir / "level_summary.csv")
    snapshot = json.loads((output_dir / "run_config.json").read_text(encoding="utf-8"))
    plot_summary_rows(output_dir, rows, snapshot)
    print(f"Concurrency figures regenerated: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
