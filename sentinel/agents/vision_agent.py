"""Vision / OCR + Layout Agent — build-map ticket #7.

Responsibility
--------------
Extract the *visually displayed total* from an invoice image or PDF, plus
layout flags (header/logo/table/signature region anomalies). Emits a
structured Claim for the contradiction engine (#15).

Processing pipeline
-------------------
1. File forensics pre-pass already ran — we receive the file path + any
   pre-extracted metrics from the ForensicsResult.
2. Text extraction:
   a. PDF  → pdfminer.six (no binary required).
   b. Image → pytesseract (requires Tesseract binary; graceful fallback).
   c. Pre-extracted text → used directly (test / demo shortcut).
3. Total extraction — regex over extracted text for dollar amounts.
4. Layout analysis — structural heuristics on text blocks.
5. Injection pre-scan on all extracted text via #6.
6. PII redaction via #4 before any text leaves this module.

Output Claim fields
-------------------
  visual_total   : float   — the largest dollar amount found on the document
  layout_anomaly : float   — 0..1, proportion of layout checks that failed
  injection_found: bool    — whether an injection was detected in the text

All claims carry source_pointers of the form  "<case_id>/invoice.png#bbox=[…]".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..claims import Claim
from ..injection_scanner import scan_fields
from ..pii_gateway import PIIRegistry, redact

log = logging.getLogger(__name__)

# ── Layout heuristic thresholds ───────────────────────────────────────────────
_MIN_VENDOR_LINE_LEN = 3  # vendor name should be ≥ 3 chars
_MIN_TOTAL_AMOUNT = 1.0  # anything < $1 is suspicious
_MAX_LINE_COUNT = 500  # a single-page invoice should not exceed this


# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class LayoutFlag:
    name: str
    detail: str
    severity: float  # 0..1


@dataclass
class VisionResult:
    case_id: str
    raw_text: str
    visual_total: Optional[float]
    layout_flags: list[LayoutFlag] = field(default_factory=list)
    injection_detected: bool = False
    source_pointers: list[str] = field(default_factory=list)
    scrubbed_text: Optional[str] = None
    registry: Optional[PIIRegistry] = None

    def to_claims(self) -> list[Claim]:
        claims: list[Claim] = []

        if self.visual_total is not None:
            claims.append(
                Claim(
                    field="visual_total",
                    value=self.visual_total,
                    confidence=0.95 if self.visual_total > 0 else 0.50,
                    source_pointer=self.source_pointers[0]
                    if self.source_pointers
                    else f"{self.case_id}/document#ocr",
                    agent="vision",
                )
            )

        if self.layout_flags:
            anomaly_score = min(
                sum(f.severity for f in self.layout_flags) / len(self.layout_flags),
                1.0,
            )
            claims.append(
                Claim(
                    field="layout_anomaly",
                    value=anomaly_score,
                    confidence=0.80,
                    source_pointer=f"{self.case_id}/document#layout",
                    agent="vision",
                )
            )

        if self.injection_detected:
            claims.append(
                Claim(
                    field="injection_present",
                    value=True,
                    confidence=0.99,
                    source_pointer=f"{self.case_id}/document#ocr_injection",
                    agent="vision",
                )
            )

        return claims


# ── Main entry point ──────────────────────────────────────────────────────────


def analyze(
    case_id: str,
    file_path: Optional[str | Path] = None,
    raw_text: Optional[str] = None,
    pre_metrics: Optional[dict] = None,
) -> VisionResult:
    """Run the vision agent on an invoice file or extracted text.

    Parameters
    ----------
    case_id:
        The active case ID (used in source_pointers).
    file_path:
        Path to PDF or image file. At least one of file_path / raw_text
        / pre_metrics must be supplied.
    raw_text:
        Pre-extracted text (skips OCR — used in tests and for text-format
        invoices).
    pre_metrics:
        Dict with pre-parsed values (e.g. from mock_agents) — highest
        priority; overrides OCR when present.

    Returns
    -------
    VisionResult with all findings.
    """
    # ── 1. Get text ───────────────────────────────────────────────────────────
    text = ""

    if pre_metrics and "visual_total" in pre_metrics:
        # Use pre-extracted metrics directly (mock/test path)
        total = float(pre_metrics["visual_total"])
        sp = [f"{case_id}/invoice.png#bbox=[410,980,120,40]"]
        return VisionResult(
            case_id=case_id,
            raw_text=f"Pre-extracted total: {total}",
            visual_total=total,
            source_pointers=sp,
        )

    if raw_text:
        text = raw_text
    elif file_path:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext == ".pdf":
            text = _extract_pdf_text(path)
        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            text = _extract_image_text(path)
        else:
            log.warning(
                "vision: unsupported file type %s — text extraction skipped", ext
            )

    if not text:
        log.warning("vision: no text extracted for case %s", case_id)
        return VisionResult(case_id=case_id, raw_text="", visual_total=None)

    # ── 2. PII redaction ──────────────────────────────────────────────────────
    scrubbed, registry = redact(text, use_ner=False, redact_amounts=False)

    # ── 3. Injection scan ─────────────────────────────────────────────────────
    inj_result = scan_fields({"ocr_text": text})

    # ── 4. Extract totals ─────────────────────────────────────────────────────
    visual_total = _extract_total(text)

    # ── 5. Layout analysis ────────────────────────────────────────────────────
    flags = _layout_analysis(text, visual_total)

    # ── 6. Source pointers ────────────────────────────────────────────────────
    sp = [f"{case_id}/invoice.png#bbox=[0,0,612,792]"]
    sp.extend(inj_result.source_pointers)

    log.info(
        "vision: case=%s total=%.2f flags=%d injection=%s",
        case_id,
        visual_total or 0.0,
        len(flags),
        inj_result.detected,
    )

    return VisionResult(
        case_id=case_id,
        raw_text=text,
        visual_total=visual_total,
        layout_flags=flags,
        injection_detected=inj_result.detected,
        source_pointers=sp,
        scrubbed_text=scrubbed,
        registry=registry,
    )


# ── Text extraction ───────────────────────────────────────────────────────────


def _extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF using pdfminer.six (no binary required)."""
    try:
        from pdfminer.high_level import extract_text  # type: ignore

        text = extract_text(str(path))
        log.info("vision: pdfminer extracted %d chars from %s", len(text), path.name)
        return text
    except Exception as e:
        log.warning("vision: pdfminer failed (%s) — falling back to raw bytes", e)
        # Last resort: read raw bytes and decode printable ASCII
        data = path.read_bytes()
        return "".join(chr(b) for b in data if 32 <= b < 127)


def _extract_image_text(path: Path) -> str:
    """Extract text from an image using pytesseract (optional dependency)."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        log.info("vision: tesseract extracted %d chars from %s", len(text), path.name)
        return text
    except ImportError:
        log.warning(
            "vision: pytesseract not installed — install with: "
            "pip install pytesseract  (also requires Tesseract binary)"
        )
        return ""
    except Exception as e:
        log.warning("vision: tesseract failed (%s)", e)
        return ""


# ── Total extraction ──────────────────────────────────────────────────────────

_TOTAL_PATTERNS = [
    # "Total Due: $12,500.00" / "TOTAL $12,500" / "Grand Total $1,200"
    re.compile(
        r"(?:total\s+due|total\s+amount|amount\s+due|grand\s+total|grand\s+total\s+due|total)[:\s]*"
        r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)",
        re.IGNORECASE,
    ),
    # Fallback: any dollar amount (take the largest)
    re.compile(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)"),
]


def _extract_total(text: str) -> Optional[float]:
    """Find the invoice total in extracted text.

    Priority: collect ALL labelled-total matches, return the largest.
    This handles invoices where both 'Subtotal' and 'Grand Total' appear —
    the Grand Total is always larger and is the correct number.
    Fallback: largest bare dollar amount on the page.
    """
    candidates: list[float] = []

    # Priority: explicit "total" label patterns — collect ALL, take largest
    for m in _TOTAL_PATTERNS[0].finditer(text):
        val = _parse_amount(m.group(1))
        if val and val >= _MIN_TOTAL_AMOUNT:
            candidates.append(val)

    if candidates:
        return max(candidates)

    # Fallback: all dollar amounts, return largest
    for m in _TOTAL_PATTERNS[1].finditer(text):
        val = _parse_amount(m.group(1))
        if val and val >= _MIN_TOTAL_AMOUNT:
            candidates.append(val)

    return max(candidates) if candidates else None


def _parse_amount(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


# ── Layout analysis ───────────────────────────────────────────────────────────


def _layout_analysis(text: str, total: Optional[float]) -> list[LayoutFlag]:
    flags: list[LayoutFlag] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Flag: suspiciously few lines (≤ 3 lines — possibly stripped/minimal)
    if len(lines) <= 3:
        flags.append(
            LayoutFlag(
                name="minimal_content",
                detail=f"Only {len(lines)} non-empty lines — document may be stripped",
                severity=0.4,
            )
        )

    # Flag: no vendor identifier found
    has_vendor = any(
        kw in text.lower()
        for kw in ("vendor", "from:", "bill from", "invoice from", "seller", "company")
    )
    if not has_vendor:
        flags.append(
            LayoutFlag(
                name="missing_vendor",
                detail="No vendor/seller identifier found in document",
                severity=0.5,
            )
        )

    # Flag: no invoice number
    has_invoice_num = bool(
        re.search(r"(?:invoice|inv|bill)\s*[#\-]?\s*\d+", text, re.IGNORECASE)
    )
    if not has_invoice_num:
        flags.append(
            LayoutFlag(
                name="missing_invoice_number",
                detail="No invoice number pattern found",
                severity=0.3,
            )
        )

    # Flag: total is suspiciously round (e.g. exactly $50,000 — common in BEC)
    if total and total >= 10_000 and total == int(total):
        flags.append(
            LayoutFlag(
                name="suspiciously_round_total",
                detail=f"Total ${total:,.0f} is a suspiciously round number",
                severity=0.35,
            )
        )

    # Flag: multiple totals that might conflict (injection obfuscation)
    all_amounts = re.findall(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text)
    parsed = [_parse_amount(a) for a in all_amounts if _parse_amount(a)]
    parsed_filtered = [v for v in parsed if v and v >= _MIN_TOTAL_AMOUNT]
    unique_amounts = set(parsed_filtered)
    if len(unique_amounts) > 4:
        flags.append(
            LayoutFlag(
                name="conflicting_amounts",
                detail=f"{len(unique_amounts)} distinct dollar amounts on one document",
                severity=0.4,
            )
        )

    return flags
