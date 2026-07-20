"""Prefixed short ids — docs/12-data-api.md."""

from __future__ import annotations

import secrets


def new_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_hex(4)}"
