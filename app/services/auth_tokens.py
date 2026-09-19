"""Hashed API tokens at rest. Secrets are never stored in the clear."""

from __future__ import annotations

import hashlib


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
