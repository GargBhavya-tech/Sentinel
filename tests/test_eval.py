"""Tests for the evaluation harness and the ablation."""

from sentinel.eval.harness import ablation, evaluate


def test_engine_recall_beats_baseline():
    a = ablation()
    assert a["on"]["recall"] > a["off"]["recall"], "cross-examination must lift recall"
    assert a["n_caught_by_engine_only"] >= 3, "engine should catch several extra frauds"


def test_precision_stays_high_no_fp():
    m = evaluate("on")
    # No false positives on the seed set -> perfect precision.
    assert m.fp == 0
    assert m.precision == 1.0


def test_baseline_still_catches_obvious_frauds():
    a = ablation()
    # The baseline is not useless — it should still catch the blatant ones.
    assert a["off"]["tp"] >= 3


def test_dataset_has_both_labels():
    from sentinel.eval.dataset import seed_dataset
    labels = {c.label for c in seed_dataset()}
    assert labels == {0, 1}
