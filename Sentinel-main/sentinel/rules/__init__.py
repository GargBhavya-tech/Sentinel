"""Detection-rule sub-package (build-map ticket #26).

Public surface:
    from sentinel.rules import engine, synthesizer, schema
"""

from .schema import Rule, RuleStatus
from .engine import match_rules
from .synthesizer import synthesize_rule

__all__ = ["Rule", "RuleStatus", "match_rules", "synthesize_rule"]
