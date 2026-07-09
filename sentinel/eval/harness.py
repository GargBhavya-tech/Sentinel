"""Evaluation harness (build-map ticket #34) — proof, not assertion.

Reports precision / recall / F1 and, crucially, the ABLATION: contradiction
engine ON vs. OFF, and how many frauds ON catches that OFF misses. That last
number is the money shot for the demo slide and the strongest possible answer to
"did you actually build this, and does it work?"

Pure stdlib — no sklearn required, so it runs anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..pipeline import run_case
from .dataset import Case, seed_dataset


@dataclass
class Metrics:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    tn: int
    fn: int
    n: int

    def as_dict(self) -> dict:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "tp": self.tp, "fp": self.fp, "tn": self.tn, "fn": self.fn, "n": self.n,
        }


def _score(cases: Iterable[Case], engine: str) -> tuple[Metrics, set[str]]:
    tp = fp = tn = fn = 0
    caught_fraud_ids: set[str] = set()
    for c in cases:
        pred = 1 if run_case(c.id, c.metrics, contradiction_engine=engine).is_flagged else 0
        if c.label == 1 and pred == 1:
            tp += 1
            caught_fraud_ids.add(c.id)
        elif c.label == 0 and pred == 1:
            fp += 1
        elif c.label == 0 and pred == 0:
            tn += 1
        else:  # label 1, pred 0
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    n = tp + fp + tn + fn
    return Metrics(precision, recall, f1, tp, fp, tn, fn, n), caught_fraud_ids


def evaluate(engine: str = "on", cases: list[Case] | None = None) -> Metrics:
    cases = cases or seed_dataset()
    metrics, _ = _score(cases, engine)
    return metrics


def ablation(cases: list[Case] | None = None) -> dict:
    """Run ON vs OFF and compute the frauds ON catches that OFF misses."""
    cases = cases or seed_dataset()
    on, on_caught = _score(cases, "on")
    off, off_caught = _score(cases, "off")
    caught_by_engine_only = sorted(on_caught - off_caught)
    return {
        "on": on.as_dict(),
        "off": off.as_dict(),
        "recall_gain": round(on.recall - off.recall, 4),
        "frauds_caught_by_engine_only": caught_by_engine_only,
        "n_caught_by_engine_only": len(caught_by_engine_only),
        "n": on.n,
    }


def headline_number(cases: list[Case] | None = None) -> str:
    """The one-line stat for the demo slide (build-map #34 / §8.5)."""
    a = ablation(cases)
    on = a["on"]
    return (
        f"Precision {on['precision']:.2f} · Recall {on['recall']:.2f} · "
        f"Contradiction engine caught {a['n_caught_by_engine_only']} frauds "
        f"single-model scoring missed (n={a['n']})"
    )
