"""Tests for the CORE + SUPPORTING gap fixes.

Covers: voice detector AUC on the curated pair (#12), file-forensics hidden
payload (#5), Red Team real session track record (#16), and adversarial
self-play catching its own fake (#17).
"""

from __future__ import annotations

from pathlib import Path

from sentinel.agents import voice_agent, red_team_agent
from sentinel.agents.adversarial_agent import run_self_play
from sentinel.claims import Claim
from sentinel import file_forensics


# ── #12 Voice: curated pair + AUC ──────────────────────────────────────────────

def test_voice_detector_separates_curated_pair():
    real, cloned = voice_agent.make_demo_voice_pair()
    real_score = voice_agent._acoustic_spoof_score(real, 16000)
    cloned_score = voice_agent._acoustic_spoof_score(cloned, 16000)
    assert cloned_score > real_score  # cloned scores more synthetic


def test_voice_validate_detector_auc_high():
    auc = voice_agent.validate_detector()
    assert auc >= 0.8  # detector cleanly separates the curated pair


def test_demo_voice_result_is_live_and_flagged():
    res = voice_agent.demo_voice_result("case-1", "U_CEO")
    assert res.detector_auc is not None
    assert res.voice_mismatch > 0.0
    assert res.to_claim().field == "voice_mismatch"


# ── #5 File forensics: hidden payload after EOF ────────────────────────────────

def test_forensics_surfaces_hidden_payload(tmp_path: Path):
    pdf = tmp_path / "demo.pdf"
    file_forensics.make_demo_artifact(pdf, message="HELLO_SENTINEL")
    result = file_forensics.scan(pdf)
    assert result.suspicious
    assert result.hidden_payloads
    assert "HELLO_SENTINEL" in (result.hidden_payloads[0].decoded or "")


# ── #16 Red Team: real per-session track record ────────────────────────────────

def test_red_team_track_record_is_real():
    red_team_agent.reset_track_record()
    claims = [
        Claim("visual_total", 500.0, 0.9, "p", "vision"),
        Claim("structured_total", 5000.0, 0.9, "p", "finance"),
    ]
    r1 = red_team_agent.generate_defense(claims, verdict="FRAUD_LIKELY")
    assert "0 of 1" in r1["track_record"]  # innocent defense was wrong
    r2 = red_team_agent.generate_defense(claims, verdict="CLEAR")
    assert "1 of 2" in r2["track_record"]  # innocent defense vindicated once


# ── #17 Adversarial self-play catches its own fake ─────────────────────────────

def test_self_play_catches_its_own_fake():
    for doc_type in ("invoice", "voice_note"):
        result = run_self_play(doc_type)
        assert result["caught_by_engine"] is True
        assert result["verdict_returned"] == "FRAUD_LIKELY"
