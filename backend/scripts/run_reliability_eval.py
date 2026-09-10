"""Run the offline reliability stress benchmark from a developer checkout.

Example:
    uv run --directory backend python scripts/run_reliability_eval.py --dataset sample
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agent.robustness import evaluate_robustness  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run seeded Agent Runtime robustness evaluation")
    parser.add_argument("--dataset", default="sample", choices=("sample", "toolluban"))
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 19, 42])
    args = parser.parse_args()

    report = evaluate_robustness(dataset=args.dataset, seeds=args.seeds)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
