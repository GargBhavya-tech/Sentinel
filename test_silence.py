"""Test Confidence-Calibrated Silence (build-map ticket #18)."""

from sentinel.pipeline import run_case
from sentinel.claims import Claim

def main():
    print("\n=== Testing Confidence-Calibrated Silence ===\n")
    
    # 1. Thin evidence (only 1 claim)
    claims_thin = [
        Claim(field="domain_age_days", value=50, confidence=0.99, source_pointer="whois", agent="threat_intel")
    ]
    v_thin = run_case(claims_thin)
    print("Test 1: Thin Evidence (<2 claims)")
    print(f"  Verdict: {v_thin.verdict}")
    print(f"  Message: {v_thin.counterfactual}\n")
    
    # 2. Low confidence
    claims_low_conf = [
        Claim(field="visual_total", value=500.0, confidence=0.2, source_pointer="page1", agent="vision"),
        Claim(field="structured_total", value=500.0, confidence=0.1, source_pointer="page2", agent="finance")
    ]
    v_low_conf = run_case(claims_low_conf)
    print("Test 2: Low Confidence (avg < 0.3)")
    print(f"  Verdict: {v_low_conf.verdict}")
    print(f"  Message: {v_low_conf.counterfactual}\n")

if __name__ == "__main__":
    main()
