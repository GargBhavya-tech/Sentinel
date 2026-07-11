"""Evidence ingestion — download a forwarded file and hand it to the agents.

This closes the biggest credibility gap in the demo: before this, the Vision
agent ran on placeholder data and never touched the actual document that was
forwarded. Now, when a Slack message carries a file (or the React console
supplies a file URL), we download the bytes to a temp file and give the real
path to `vision_agent.analyze`, which extracts the *actually displayed* total —
the number the contradiction engine cross-examines.

Slack's `url_private` requires `Authorization: Bearer <bot token>`; public URLs
don't. Everything here fails soft: any error returns None and the pipeline
falls back to its previous behaviour, so a bad/expired URL can never crash an
investigation.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

log = logging.getLogger(__name__)

# Guardrails: cap download size and only accept types the agents can read.
_MAX_BYTES = 15 * 1024 * 1024  # 15 MB
_SUPPORTED = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt", ".csv"}

_CTYPE_SUFFIX = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
    "text/plain": ".txt",
    "text/csv": ".csv",
}


def _suffix_for(filename: Optional[str], content_type: str) -> str:
    """Pick a file suffix from the Slack filename first, then Content-Type."""
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in _SUPPORTED:
            return ext
    return _CTYPE_SUFFIX.get(content_type.split(";")[0].strip().lower(), ".bin")


async def download_evidence(
    url: str,
    *,
    slack_token: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[str]:
    """Download `url` to a temp file and return its path (or None on failure).

    Parameters
    ----------
    url:          The file URL. For Slack, this is `file.url_private`.
    slack_token:  Bot token; sent as a Bearer header only for slack.com URLs.
    filename:     Original filename (used to infer the extension).
    """
    if not url:
        return None

    # Local path (e.g. a browser-uploaded evidence file) — copy to a temp file
    # so the caller's cleanup deletes the copy, not the stored upload.
    if os.path.isfile(url):
        try:
            fd, path = tempfile.mkstemp(suffix=Path(url).suffix, prefix="sentinel_ev_")
            os.close(fd)
            shutil.copyfile(url, path)
            return path
        except OSError as e:
            log.warning("ingest: could not copy local evidence %s: %s", url, e)
            return None

    try:
        import httpx  # type: ignore

        headers: dict[str, str] = {}
        token = slack_token or os.environ.get("SLACK_BOT_TOKEN", "")
        if token and "slack.com" in url:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code != 200:
            log.warning("ingest: download failed %s (HTTP %s)", url, resp.status_code)
            return None

        content_type = resp.headers.get("content-type", "")
        # Slack returns an HTML login page (200) if the token is missing/wrong.
        if "text/html" in content_type and "slack.com" in url:
            log.warning(
                "ingest: Slack returned HTML (not the file) — is SLACK_BOT_TOKEN "
                "set and does it have files:read? url=%s",
                url,
            )
            return None

        data = resp.content[:_MAX_BYTES]
        if not data:
            log.warning("ingest: empty body for %s", url)
            return None

        suffix = _suffix_for(filename, content_type)
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="sentinel_ev_")
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        log.info(
            "ingest: saved %d bytes from %s -> %s (%s)",
            len(data), filename or url, path, content_type or "unknown",
        )
        return path

    except Exception as e:  # network error, bad URL, httpx missing, etc.
        log.warning("ingest: error downloading %s: %s", url, e)
        return None


def cleanup_evidence(path: Optional[str]) -> None:
    """Best-effort delete of a temp evidence file once the agents are done."""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


# ── Browser uploads (POST /api/upload) ─────────────────────────────────────────

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "sentinel_uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_uploads: dict[str, str] = {}  # evidence_id -> stored path (same process)


def save_upload(data: bytes, filename: str) -> str:
    """Persist an uploaded file and return an opaque evidence_id."""
    ext = Path(filename or "").suffix.lower()
    if ext not in _SUPPORTED:
        ext = ".bin"
    evidence_id = uuid4().hex
    path = _UPLOAD_DIR / f"{evidence_id}{ext}"
    path.write_bytes(data[:_MAX_BYTES])
    _uploads[evidence_id] = str(path)
    log.info("ingest: stored upload %r (%d bytes) -> %s", filename, len(data), path)
    return evidence_id


def resolve_upload(evidence_id: str) -> Optional[str]:
    """Map an evidence_id back to its stored path (or None if unknown)."""
    return _uploads.get(evidence_id) if evidence_id else None


def first_supported_file(files: list[dict]) -> Optional[dict]:
    """Pick the first Slack file dict whose type the agents can actually read."""
    for f in files or []:
        name = (f.get("name") or "").lower()
        ext = Path(name).suffix.lower()
        mimetype = (f.get("mimetype") or "").lower()
        if ext in _SUPPORTED or any(
            ct in mimetype for ct in ("pdf", "image", "text", "csv")
        ):
            return f
    return None
