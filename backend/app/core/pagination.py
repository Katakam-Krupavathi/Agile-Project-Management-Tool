import base64
import json
from typing import Any

from app.core.errors import BadRequestError


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(f"{cursor}{padding}".encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR") from exc
    if not isinstance(data, dict):
        raise BadRequestError("Invalid pagination cursor.", code="INVALID_CURSOR")
    return data
