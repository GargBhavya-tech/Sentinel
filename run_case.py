"""Run a single case through the contradiction engine and print the verdict.

Usage:
    python run_case.py            # runs the flagship contradiction-only case
    python run_case.py --off      # same case through the single-model baseline
"""

from __future__ import annotations

import sys

from sentinel.eval.dataset import flagship_case
from sentinel.pipeline import run_case
from sentinel.agents.mock_agents import extract_claims


def main() -> None:
    engine = "off" if "--off" in sys.argv else "on"
    case = flagship_case()
    claims = extract_claims(case.id, case.metrics)
    v = run_case(claims, contradiction_engine=engine)

    print(f"\nCase {case.id}  [ground truth: {'FRAUD' if case.label else 'LEGIT'}]")
    print(f"  {case.note}")
    print(f"\nEngine: contradiction={engine}")
    print(f"  Verdict : {v.verdict}   (risk {v.risk})")
    if v.contradictions:
        print("  Cross-examination:")
        for c in v.contradictions:
            print(f"    - [{c.axis}] {c.detail}  (weight {c.weight})")
            for e in c.evidence:
                print(f"        source: {e}")
    else:
        print("  Cross-examination: (none — no axes fired)")
    if v.counterfactual:
        print(f"  Counterfactual: {v.counterfactual}")
    print()
    if engine == "off" and not v.is_flagged:
        print("  >>> The single-model baseline MISSED this fraud.")
        print("  >>> Re-run without --off to see the contradiction engine catch it.\n")


if __name__ == "__main__":
    main()
