"""Run the evaluation harness and print metrics + the ON-vs-OFF ablation.

Build-map ticket #34 — Evaluation Harness + Flagship Case.
This is the single biggest credibility lever for the demo.

Usage:
    python run_eval.py            # full eval
    python run_eval.py --quiet    # headline number only
    python run_eval.py --json     # machine-readable JSON output
"""

from __future__ import annotations

import json
import sys

from sentinel.eval.harness import ablation, headline_number, evaluate
from sentinel.eval.dataset import seed_dataset, flagship_case


def main() -> None:
    quiet = "--quiet" in sys.argv
    as_json = "--json" in sys.argv

    a = ablation()

    if as_json:
        print(json.dumps(a, indent=2))
        return

    cases = seed_dataset()
    n_fraud = sum(1 for c in cases if c.label == 1)
    n_legit = sum(1 for c in cases if c.label == 0)
    n_fp_traps = sum(1 for c in cases if c.family == "fp_trap")

    if not quiet:
        print("\n" + "=" * 60)
        print("  SENTINEL EVALUATION HARNESS  (build-map ticket #34)")
        print("=" * 60)
        print(f"\nDataset: {len(cases)} cases  "
              f"({n_fraud} fraud - {n_legit} legit - {n_fp_traps} FP traps)")

        print("\n-- Flagship case verification ------------------------------")
        fc = flagship_case()
        from sentinel.agents.mock_agents import extract_claims
        from sentinel.pipeline import run_case
        fc_claims = extract_claims(fc.id, fc.metrics)
        fc_on = run_case(fc_claims, "on")
        fc_off = run_case(fc_claims, "off")
        print(f"  Engine ON  -> {fc_on.verdict} (risk={fc_on.risk:.2f})")
        print(f"  Engine OFF -> {fc_off.verdict} (risk={fc_off.risk:.2f})")
        print(f"  - Flagship fraud caught: {fc_on.verdict == 'FRAUD_LIKELY'}")
        print(f"  - Single-model baseline misses it: {not fc_off.is_flagged}")

        print("\n-- Full dataset results ------------------------------------")
        on = a["on"]
        off = a["off"]

        header = f"  {'Metric':<18} {'Engine ON':>12} {'Engine OFF':>12}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for metric in ["precision", "recall", "f1"]:
            print(f"  {metric:<18} {on[metric]:>12.4f} {off[metric]:>12.4f}")
        print(f"  {'TP/FP/TN/FN':<18} "
              f"{'%d/%d/%d/%d' % (on['tp'],on['fp'],on['tn'],on['fn']):>12}  "
              f"{'%d/%d/%d/%d' % (off['tp'],off['fp'],off['tn'],off['fn']):>12}")

        print(f"\n  Recall gain from cross-examination: +{a['recall_gain']:.4f}")
        print(f"  Frauds engine catches that baseline misses: "
              f"{a['n_caught_by_engine_only']}")
        print(f"  Case IDs: {a['frauds_caught_by_engine_only']}")

    print("\n-- Demo headline (the slide number) --------------------------")
    print(f"  {headline_number()}")
    print()


if __name__ == "__main__":
    main()
