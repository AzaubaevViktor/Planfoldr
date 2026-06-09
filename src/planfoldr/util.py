"""Small shared helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def now_iso() -> str:
    """UTC timestamp in ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"
