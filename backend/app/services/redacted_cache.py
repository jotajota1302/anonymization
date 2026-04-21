"""Disk-backed cache for Presidio-redacted image attachments.

Avoids re-running OCR + Presidio on every view. Cached PNGs live in
`data/redacted_cache/<source_ticket_id>__<filename>.png`.
"""

from pathlib import Path
from typing import Optional
import hashlib

import structlog

logger = structlog.get_logger()

_CACHE_ROOT = Path("data/redacted_cache")


def _sanitize(name: str) -> str:
    """Filesystem-safe filename component."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in name)[:120]


def _cache_path(source_ticket_id: str, filename: str) -> Path:
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    key = f"{_sanitize(source_ticket_id)}__{_sanitize(filename)}"
    # suffix with short hash to avoid collisions on truncation
    h = hashlib.sha1(f"{source_ticket_id}/{filename}".encode("utf-8")).hexdigest()[:8]
    return _CACHE_ROOT / f"{key}.{h}.png"


def get(source_ticket_id: str, filename: str) -> Optional[bytes]:
    p = _cache_path(source_ticket_id, filename)
    if p.exists():
        try:
            return p.read_bytes()
        except OSError as e:
            logger.warning("redacted_cache_read_failed", path=str(p), error=str(e))
    return None


def put(source_ticket_id: str, filename: str, content: bytes) -> None:
    p = _cache_path(source_ticket_id, filename)
    try:
        p.write_bytes(content)
        logger.info("redacted_cache_stored", path=str(p), size=len(content))
    except OSError as e:
        logger.warning("redacted_cache_write_failed", path=str(p), error=str(e))
