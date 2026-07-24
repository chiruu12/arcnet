"""Optional write auth — localhost-trust by default (docs/12, docs/32)."""

from __future__ import annotations

import hmac
import os

from fastapi import Request

from arcnet_server.errors import api_error

WRITE_SECRET_HEADER = "X-Arcnet-Write-Secret"


def write_secret_configured() -> bool:
    return bool(os.getenv("ARCNET_WRITE_SECRET", "").strip())


def _read_write_secret(request: Request) -> str:
    got = (request.headers.get("x-arcnet-write-secret") or "").strip()
    if got:
        return got
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def require_write_auth(request: Request) -> None:
    """When ARCNET_WRITE_SECRET is unset → allow (demo default). When set → require header."""
    expected = os.getenv("ARCNET_WRITE_SECRET", "").strip()
    if not expected:
        return
    got = _read_write_secret(request)
    if not got or not hmac.compare_digest(got, expected):
        raise api_error(
            401,
            "invalid or missing write secret",
            hint=f"set header {WRITE_SECRET_HEADER} to match ARCNET_WRITE_SECRET",
        )
