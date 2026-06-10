"""Small shared helpers."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

_cycle_seq_lock = threading.Lock()
_cycle_seq = 0


def now_iso() -> str:
    """UTC timestamp in ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def next_cycle_seq() -> int:
    global _cycle_seq
    with _cycle_seq_lock:
        _cycle_seq += 1
        return _cycle_seq
