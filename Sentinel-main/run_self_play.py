"""Run the Adversarial Self-Play routine (build-map ticket #17).

Usage:
    python run_self_play.py
"""

import sys
from sentinel.agents.adversarial_agent import run_self_play

def main():
    print("\n=== Sentinel Adversarial Self-Play ===\n")
    
    # Test invoice fake
    res1 = run_self_play("invoice")
    print(f"Fake Invoice Test: {'CAUGHT' if res1['caught_by_engine'] else 'MISSED'} "
          f"(Contradictions: {', '.join(res1['contradictions_found'])})")
          
    # Test voice fake
    res2 = run_self_play("voice_note")
    print(f"Fake Voice Note Test: {'CAUGHT' if res2['caught_by_engine'] else 'MISSED'} "
          f"(Contradictions: {', '.join(res2['contradictions_found'])})")
          
    print("\nDone.")

if __name__ == "__main__":
    main()
