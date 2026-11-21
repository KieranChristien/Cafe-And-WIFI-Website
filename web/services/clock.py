from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_current_time() -> datetime:
    return datetime.now(timezone.utc)


def get_local_now(current_time: datetime, timezone_name: str | None) -> datetime | None:
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("current_time must be timezone-aware")

    if not timezone_name:
        return None

    try:
        return current_time.astimezone(
            ZoneInfo(timezone_name)
        )

    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None
