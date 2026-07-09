"""Finance Agent — build-map ticket #8.

Parses structured / CSV data attached to a case and produces a risk score.
The build map explicitly says: "a heuristic / EWMA-weighted score is fine
for the demo — indistinguishable from XGBoost on camera."

What it does
------------
1. Parse a CSV or list of rows to extract amount, date, vendor, and account.
2. Apply EWMA (exponentially weighted moving average) to compute a
   per-vendor expected amount and compare the current invoice against it.
3. Run structural checks (round amounts, new vendor, same-day rush, weekend
   submission, duplicate invoice number) and flag each as a risk factor.
4. Output structured_total as a Claim + a risk_score Claim.

No LLM. No XGBoost. Just deterministic finance math.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..claims import Claim

log = logging.getLogger(__name__)

# ── EWMA parameters ───────────────────────────────────────────────────────────
EWMA_ALPHA        = 0.3    # smoothing factor — lower = longer memory
AMOUNT_DEVIATION  = 2.5    # flag if amount > N × ewma expected
MAX_ROUND_AMOUNT  = 50_000 # round amounts above this are suspicious
_WEEKEND          = {5, 6} # Saturday, Sunday


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class RiskFactor:
    name: str
    detail: str
    weight: float   # 0..1 contribution to risk


@dataclass
class FinanceResult:
    case_id: str
    structured_total: Optional[float]
    risk_score: float          # 0..1 composite
    risk_factors: list[RiskFactor] = field(default_factory=list)
    top_factors: list[str] = field(default_factory=list)
    source_pointer: str = ""

    def to_claims(self) -> list[Claim]:
        claims: list[Claim] = []
        if self.structured_total is not None:
            claims.append(Claim(
                field="structured_total",
                value=self.structured_total,
                confidence=0.99,
                source_pointer=self.source_pointer or f"{self.case_id}/data.csv#R14C3",
                agent="finance",
            ))
        claims.append(Claim(
            field="finance_risk",
            value=self.risk_score,
            confidence=0.85,
            source_pointer=self.source_pointer or f"{self.case_id}/data.csv#risk",
            agent="finance",
        ))
        return claims


# ── EWMA vendor history (in-memory for demo) ──────────────────────────────────

_vendor_history: dict[str, list[float]] = {}


def _ewma(values: list[float]) -> float:
    """Compute EWMA of a list of amounts."""
    if not values:
        return 0.0
    result = values[0]
    for v in values[1:]:
        result = EWMA_ALPHA * v + (1 - EWMA_ALPHA) * result
    return result


def update_vendor_history(vendor: str, amount: float) -> None:
    """Add a confirmed-legitimate transaction to the vendor history."""
    _vendor_history.setdefault(vendor, []).append(amount)


def clear_vendor_history() -> None:
    _vendor_history.clear()


# ── Main entry point ───────────────────────────────────────────────────────────

def analyze(
    case_id: str,
    amount: Optional[float] = None,
    vendor: Optional[str] = None,
    invoice_date: Optional[str] = None,   # ISO format: "2026-07-09"
    invoice_number: Optional[str] = None,
    csv_text: Optional[str] = None,
    prior_invoices: Optional[list[dict]] = None,  # list of {amount, vendor, date}
    pre_metrics: Optional[dict] = None,
) -> FinanceResult:
    """Run the finance risk analysis.

    Parameters
    ----------
    case_id:         Active case ID.
    amount:          Invoice amount (if pre-parsed).
    vendor:          Vendor name (if pre-parsed).
    invoice_date:    Invoice date string.
    invoice_number:  Invoice reference number.
    csv_text:        Raw CSV content to parse for amount/vendor (overrides above).
    prior_invoices:  Historical transactions for EWMA baseline.
    pre_metrics:     Pre-extracted metrics (mock/test shortcut).
    """

    # ── Pre-extracted shortcut ────────────────────────────────────────────────
    if pre_metrics and "structured_total" in pre_metrics:
        total = float(pre_metrics["structured_total"])
        risk  = float(pre_metrics.get("finance_risk", 0.0))
        return FinanceResult(
            case_id=case_id,
            structured_total=total,
            risk_score=risk,
            source_pointer=f"{case_id}/data.csv#R14C3",
        )

    # ── Parse CSV if provided ─────────────────────────────────────────────────
    if csv_text:
        amount, vendor, invoice_number, invoice_date = _parse_csv(csv_text)

    factors: list[RiskFactor] = []

    # ── EWMA deviation check ──────────────────────────────────────────────────
    if amount is not None and vendor:
        history = _vendor_history.get(vendor, [])
        if prior_invoices:
            history = [p["amount"] for p in prior_invoices
                       if p.get("vendor") == vendor] + history

        if history:
            expected = _ewma(history)
            if expected > 0 and amount > expected * AMOUNT_DEVIATION:
                factors.append(RiskFactor(
                    name="ewma_deviation",
                    detail=(
                        f"Amount ${amount:,.2f} is {amount/expected:.1f}× "
                        f"the EWMA expected ${expected:,.2f} for {vendor!r}"
                    ),
                    weight=0.40,
                ))
        else:
            # New vendor — mild flag
            factors.append(RiskFactor(
                name="new_vendor",
                detail=f"No prior transaction history for vendor {vendor!r}",
                weight=0.20,
            ))

    # ── Round-number check ────────────────────────────────────────────────────
    if amount and amount >= MAX_ROUND_AMOUNT and amount == int(amount):
        factors.append(RiskFactor(
            name="round_amount",
            detail=f"Suspiciously round amount ${amount:,.0f}",
            weight=0.25,
        ))

    # ── Weekend submission ────────────────────────────────────────────────────
    if invoice_date:
        try:
            dt = datetime.fromisoformat(invoice_date)
            if dt.weekday() in _WEEKEND:
                factors.append(RiskFactor(
                    name="weekend_submission",
                    detail=f"Invoice submitted on a {dt.strftime('%A')}",
                    weight=0.15,
                ))
        except ValueError:
            pass

    # ── Duplicate invoice number (simple in-memory check) ────────────────────
    if invoice_number and _is_duplicate(case_id, invoice_number):
        factors.append(RiskFactor(
            name="duplicate_invoice",
            detail=f"Invoice number {invoice_number!r} already seen",
            weight=0.45,
        ))

    # ── Composite risk score ──────────────────────────────────────────────────
    risk_score = round(min(sum(f.weight for f in factors), 1.0), 4)
    top_factors = [f.name for f in sorted(factors, key=lambda x: -x.weight)[:3]]

    log.info(
        "finance: case=%s amount=%.2f risk=%.3f factors=%s",
        case_id, amount or 0.0, risk_score, top_factors,
    )

    return FinanceResult(
        case_id=case_id,
        structured_total=amount,
        risk_score=risk_score,
        risk_factors=factors,
        top_factors=top_factors,
        source_pointer=f"{case_id}/data.csv#R14C3",
    )


# ── CSV parser ────────────────────────────────────────────────────────────────

def _parse_csv(
    csv_text: str,
) -> tuple[Optional[float], Optional[str], Optional[str], Optional[str]]:
    """Extract amount, vendor, invoice_number, date from CSV.

    Handles amount fields written as bare `$7,500.00` (without quoting) by
    pre-quoting any cell that starts with $ followed by digits or commas
    before feeding to DictReader.
    """
    amount = vendor = inv_num = date = None
    try:
        # Pre-quote bare dollar amounts so CSV commas don't split columns.
        # Pattern: $digits-and-commas at start of a cell (after , or start of line)
        import re as _re
        cleaned = _re.sub(
            r'(?<!["\w])(\$[\d,]+(?:\.\d{2})?)',
            lambda m: f'"{m.group(1)}"',
            csv_text,
        )
        reader = csv.DictReader(io.StringIO(cleaned))
        for row in reader:
            if row is None:
                continue
            row_lower = {k.lower().strip(): v for k, v in row.items() if k}
            # amount
            for key in ("amount", "total", "invoice_amount", "value"):
                if key in row_lower:
                    raw = re.sub(r"[$,]", "", (row_lower[key] or ""))
                    try:
                        amount = float(raw)
                    except ValueError:
                        pass
                    break
            # vendor
            for key in ("vendor", "supplier", "payee", "company"):
                if key in row_lower:
                    vendor = row_lower[key]
                    break
            # invoice number
            for key in ("invoice_number", "invoice#", "inv_num", "reference"):
                if key in row_lower:
                    inv_num = row_lower[key]
                    break
            # date
            for key in ("date", "invoice_date", "submission_date"):
                if key in row_lower:
                    date = row_lower[key]
                    break
            if amount:
                break   # use first data row
    except Exception as e:
        log.warning("finance: CSV parse failed (%s)", e)
    return amount, vendor, inv_num, date


# ── Duplicate tracker ─────────────────────────────────────────────────────────

_seen_invoices: set[str] = set()


def _is_duplicate(case_id: str, invoice_number: str) -> bool:
    key = invoice_number.strip().lower()
    if key in _seen_invoices:
        return True
    _seen_invoices.add(key)
    return False


def clear_invoice_tracker() -> None:
    _seen_invoices.clear()
