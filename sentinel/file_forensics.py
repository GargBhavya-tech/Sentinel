"""File Forensics Pre-Pass — build-map ticket #5.

Every file attached to a case passes through this module BEFORE any
OCR/Vision agent touches it. It looks for two categories of hidden content:

1. High-entropy byte windows
   Shannon entropy across 256-byte windows. Entropy > 7.2 bits/byte strongly
   suggests compressed/encrypted/obfuscated data embedded in the file.

2. Data appended after the structural EOF marker
   - PDF:  bytes after the last %%EOF
   - PNG:  bytes after the IEND chunk
   - JPEG: bytes after the FFD9 (EOI) marker
   - ZIP / Office (OOXML): trailing bytes after the end-of-central-directory
   If anything non-trivial (> 8 bytes, non-whitespace) is found, it is
   extracted and surfaced as evidence.

The demo artifact (see #5 in the build map) is a PDF with a single-byte
XOR-obfuscated payload appended after %%EOF. `make_demo_artifact()` in
this module creates that file so the beat is always reliable.

Returns
-------
ForensicsResult — a dataclass with:
  suspicious: bool
  entropy_anomalies: list[EntropyAnomaly]  — high-entropy windows
  hidden_payloads: list[HiddenPayload]     — post-EOF data
  source_pointers: list[str]              — for click-to-source in the UI

No LLM involved at any point — purely deterministic byte math.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

ENTROPY_WINDOW = 256  # bytes per sliding window
ENTROPY_THRESHOLD = 7.2  # bits/byte — above this = suspicious
MIN_PAYLOAD_BYTES = 8  # ignore trailing whitespace / padding < this
XOR_KEY = 0x42  # demo artifact XOR key (arbitrary; documented)


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass
class EntropyAnomaly:
    offset: int  # byte offset of the window start
    entropy: float  # measured Shannon entropy (bits/byte)
    snippet_hex: str  # first 16 bytes as hex (for the UI card)


@dataclass
class HiddenPayload:
    offset: int  # byte offset where the payload starts
    raw_bytes: bytes  # raw extracted bytes
    decoded: Optional[str] = None  # XOR-decoded text if printable
    encoding: str = "raw"  # "raw" | "xor-0xNN"

    @property
    def preview(self) -> str:
        """Short human-readable preview for the Slack card."""
        if self.decoded:
            return self.decoded[:120]
        return self.raw_bytes[:60].hex()


@dataclass
class ForensicsResult:
    file_path: str
    file_size_bytes: int
    suspicious: bool
    entropy_anomalies: list[EntropyAnomaly] = field(default_factory=list)
    hidden_payloads: list[HiddenPayload] = field(default_factory=list)
    source_pointers: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        parts = []
        if self.entropy_anomalies:
            parts.append(f"{len(self.entropy_anomalies)} high-entropy window(s)")
        if self.hidden_payloads:
            parts.append(f"{len(self.hidden_payloads)} hidden payload(s) after EOF")
        return "; ".join(parts) if parts else "clean"


# ── EOF marker lookup ─────────────────────────────────────────────────────────

_EOF_MARKERS: dict[str, list[bytes]] = {
    ".pdf": [b"%%EOF", b"%%EOF\r", b"%%EOF\n", b"%%EOF\r\n"],
    ".png": [b"\x00\x00\x00\x00IEND\xaeB`\x82"],  # IEND chunk with CRC
    ".jpg": [b"\xff\xd9"],
    ".jpeg": [b"\xff\xd9"],
    ".zip": [b"PK\x05\x06"],  # end-of-central-directory signature
    ".docx": [b"PK\x05\x06"],
    ".xlsx": [b"PK\x05\x06"],
}


# ── Main entry point ──────────────────────────────────────────────────────────


def scan(file_path: str | Path) -> ForensicsResult:
    """Run the full forensic pre-pass on a file.

    Parameters
    ----------
    file_path:
        Absolute or relative path to the file to scan.

    Returns
    -------
    ForensicsResult with all findings.
    """
    path = Path(file_path)
    data = path.read_bytes()
    ext = path.suffix.lower()

    result = ForensicsResult(
        file_path=str(path),
        file_size_bytes=len(data),
        suspicious=False,
    )

    # ── Entropy scan ──────────────────────────────────────────────────────────
    _scan_entropy(data, result)

    # ── Post-EOF payload scan ─────────────────────────────────────────────────
    _scan_eof(data, ext, result, str(path))

    result.suspicious = bool(result.entropy_anomalies or result.hidden_payloads)

    if result.suspicious:
        log.warning("forensics: SUSPICIOUS — %s — %s", path.name, result.summary)
    else:
        log.info("forensics: clean — %s", path.name)

    return result


# ── Entropy scanner ───────────────────────────────────────────────────────────


def _shannon_entropy(data: bytes) -> float:
    """Shannon entropy in bits/byte for a byte sequence."""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    entropy = 0.0
    for count in freq:
        if count:
            p = count / n
            entropy -= p * math.log2(p)
    return entropy


def _scan_entropy(data: bytes, result: ForensicsResult) -> None:
    """Slide a window over the file and record high-entropy regions."""
    step = ENTROPY_WINDOW // 2  # 50 % overlap
    for offset in range(0, len(data) - ENTROPY_WINDOW, step):
        window = data[offset : offset + ENTROPY_WINDOW]
        entropy = _shannon_entropy(window)
        if entropy > ENTROPY_THRESHOLD:
            anomaly = EntropyAnomaly(
                offset=offset,
                entropy=round(entropy, 3),
                snippet_hex=window[:16].hex(),
            )
            result.entropy_anomalies.append(anomaly)
            result.source_pointers.append(f"{result.file_path}#entropy_window@{offset}")
    # Deduplicate adjacent windows (only keep the local max per region)
    if result.entropy_anomalies:
        result.entropy_anomalies = _dedup_anomalies(result.entropy_anomalies, step)


def _dedup_anomalies(
    anomalies: list[EntropyAnomaly], step: int
) -> list[EntropyAnomaly]:
    """Keep only the highest-entropy anomaly per 512-byte region."""
    seen: dict[int, EntropyAnomaly] = {}
    for a in anomalies:
        bucket = a.offset // 512
        if bucket not in seen or a.entropy > seen[bucket].entropy:
            seen[bucket] = a
    return sorted(seen.values(), key=lambda x: x.offset)


# ── Post-EOF payload scanner ──────────────────────────────────────────────────


def _scan_eof(data: bytes, ext: str, result: ForensicsResult, label: str) -> None:
    """Find the last occurrence of known EOF markers and inspect what follows."""
    markers = _EOF_MARKERS.get(ext, [])
    if not markers:
        return  # unsupported file type — skip post-EOF check

    best_pos = -1
    for marker in markers:
        pos = data.rfind(marker)  # last occurrence
        if pos != -1:
            candidate = pos + len(marker)
            if candidate > best_pos:
                best_pos = candidate

    if best_pos == -1:
        return  # no recognised EOF marker — might be a corrupt/unknown file

    trailer = data[best_pos:]

    # Strip benign trailing whitespace / newlines
    trailer_stripped = trailer.strip(b"\x00\t\n\r \xff")
    if len(trailer_stripped) < MIN_PAYLOAD_BYTES:
        return  # nothing significant

    payload = HiddenPayload(
        offset=best_pos,
        raw_bytes=trailer_stripped,
    )

    # Attempt XOR decode with the known demo key
    decoded_bytes = bytes(b ^ XOR_KEY for b in trailer_stripped)
    try:
        decoded_str = decoded_bytes.decode("utf-8")
        if decoded_str.isprintable():
            payload.decoded = decoded_str
            payload.encoding = f"xor-0x{XOR_KEY:02X}"
    except UnicodeDecodeError:
        pass

    result.hidden_payloads.append(payload)
    result.source_pointers.append(f"{label}#hidden_payload@{best_pos}")


# ── Demo artifact factory ─────────────────────────────────────────────────────


def make_demo_artifact(
    dest: str | Path, message: str = "SENTINEL_DEMO_PAYLOAD"
) -> Path:
    """Create a minimal valid PDF with a XOR-obfuscated payload after %%EOF.

    This is the #5 build-map demo artifact — a file that is structurally a
    real (tiny) PDF but has a single-byte-XOR payload hidden after the last
    %%EOF. Sentinel's forensic pre-pass reliably surfaces it.

    Parameters
    ----------
    dest:
        Path where the demo PDF will be written (e.g. "demo_invoice.pdf").
    message:
        Plaintext payload to obfuscate and embed.

    Returns the path of the created file.
    """
    path = Path(dest)

    # Minimal 1-page PDF body (valid, renderable)
    pdf_body = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer << /Size 4 /Root 1 0 R >>
startxref
190
%%EOF
"""

    # XOR-obfuscate the payload
    hidden = bytes(b ^ XOR_KEY for b in message.encode("utf-8"))

    path.write_bytes(pdf_body + hidden)
    log.info(
        "forensics: demo artifact written → %s (%d bytes)", path, path.stat().st_size
    )
    return path
