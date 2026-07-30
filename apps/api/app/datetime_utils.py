"""UTC datetime helpers for API payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def utc_isoformat(value: Optional[datetime]) -> Optional[str]:
    """Serialize database UTC datetimes with an explicit timezone marker."""

    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")
