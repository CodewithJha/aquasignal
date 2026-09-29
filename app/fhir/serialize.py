"""Canonical Bundle serialization + deterministic content hash."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bundle_json(bundle: dict[str, Any]) -> str:
    """Deterministic JSON: sorted keys, compact separators, UTF-8 safe."""
    return json.dumps(
        bundle,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def bundle_content_hash(bundle: dict[str, Any]) -> str:
    """SHA-256 hex digest of canonical Bundle bytes (HITL Q6)."""
    payload = canonical_bundle_json(bundle).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
