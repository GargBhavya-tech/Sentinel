"""Run the evaluation harness and print metrics + the ON-vs-OFF ablation.

Usage:
    python run_eval.py
"""

from __future__ import annotations

import json

from sentinel.eval.harness import ablation, headline_number


def main() -> None:
    a = ablation()
    print("\n=== Sentinel Evaluation Harness ===\n")
    print("Contradiction engine ON :", json.dumps(a["on"]))
    print("Contradiction engine OFF:", json.dumps(a["off"]))
    print(f"\nRecall gain from cross-examination: +{a['recall_gain']:.2f}")
    print(f"Frauds caught by the engine but missed by single-model scoring: "
          f"{a['n_caught_by_engine_only']}  {a['frauds_caught_by_engine_only']}")
    print("\n--- Demo headline number ---")
    print(headline_number())
    print()


if __name__ == "__main__":
    main()
