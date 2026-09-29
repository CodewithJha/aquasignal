"""Pseudonymous observer reference — per-browser handle, no personal identity.

A random 128-bit token lives only in the observer's ``cg_observer`` cookie.
Storage keeps ``observer_ref`` = SHA-256 over a fixed domain-separation prefix
and the token, so the token itself is never persisted, logged, or displayed.

The display pseudonym is ``Observer-`` + the first 8 hex characters of the
ref (uppercase), i.e. 32 bits / 4,294,967,296 labels. Two observers can still
share a label (birthday bound): about 0.0001% chance among 100 observers,
0.012% among 1,000, 1.2% among 10,000. A label is a readable handle for telling
submissions apart, not a unique or verified identity. A cleared cookie or a
second browser yields a new pseudonym for the same person.
"""

from __future__ import annotations

import hashlib
import re
import secrets

from app.domain.errors import DomainValidationError

OBSERVER_COOKIE = "cg_observer"
OBSERVER_REF_PREFIX = b"confirmgate/observer-ref/v1\x00"
PSEUDONYM_HEX_CHARS = 8
PSEUDONYM_PREFIX = "Observer-"
UNKNOWN_OBSERVER_LABEL = "Observer unknown (pre-pseudonym)"

_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_REF_RE = re.compile(r"^[0-9a-f]{64}$")


def new_observer_token() -> str:
    return secrets.token_hex(16)


def is_observer_token(value: object) -> bool:
    return isinstance(value, str) and bool(_TOKEN_RE.match(value))


def is_observer_ref(value: object) -> bool:
    return isinstance(value, str) and bool(_REF_RE.match(value))


def observer_ref_for_token(token: str) -> str:
    if not is_observer_token(token):
        raise DomainValidationError("observer token must be 32 lowercase hex characters")
    return hashlib.sha256(OBSERVER_REF_PREFIX + token.encode("ascii")).hexdigest()


def observer_pseudonym(observer_ref: str | None) -> str:
    """Display label for a stored ref; rows without one are never given a fake name."""
    if not is_observer_ref(observer_ref):
        return UNKNOWN_OBSERVER_LABEL
    return PSEUDONYM_PREFIX + observer_ref[:PSEUDONYM_HEX_CHARS].upper()
