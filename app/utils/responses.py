"""Uniform JSON response envelope.

Every endpoint returns the same shape so clients never have to guess:

    {"success": true,  "data": ..., "meta": {...}}
    {"success": false, "error": {"code": "...", "message": "...", "details": ...}}
"""

from typing import Any


def ok(data: Any = None, status: int = 200, **meta: Any) -> tuple[dict, int]:
    """Build a success payload. Extra kwargs land in `meta`."""
    body: dict[str, Any] = {"success": True, "data": data}
    if meta:
        body["meta"] = meta
    return body, status


def fail(
    code: str,
    message: str,
    status: int = 400,
    details: Any = None,
) -> tuple[dict, int]:
    """Build an error payload with a machine-readable `code`."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}, status
