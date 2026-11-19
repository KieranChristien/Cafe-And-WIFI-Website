from datetime import datetime, timezone

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from web.models import Cafe


def get_operating_status(
        cafe: Cafe,
        current_time: datetime | None = None,
) -> str:
    """
    Determine whether a café is currently open.

    Returns:
        "open"
        "closed"
        "unknown"

    current_time must be timezone-aware if provided.
    If omitted, the current UTC time is used.
    """

    # Manual closure always takes priority.
    if cafe.is_manually_closed:
        return "closed"

    # Obtain the current UTC time.
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Reject naive datetimes to prevent ambiguous comparisons.
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError(
            "current_time must be timezone-aware"
        )

    # Convert to the cafe's local timezone.
    try:
        local_time = current_time.astimezone(
            ZoneInfo(cafe.timezone.__str__())
        )
    except (ZoneInfoNotFoundError, TypeError):
        raise ValueError(
            f"Invalid timezone: {cafe.timezone!r}"
        )

    current_clock = local_time.time().replace(tzinfo=None)

    # Build a weekday lookup.
    hours_by_day = {
        entry.weekday: entry
        for entry in cafe.opening_hours
    }

    today = local_time.weekday()
    yesterday = (today - 1) % 7

    today_hours = hours_by_day.get(today)
    yesterday_hours = hours_by_day.get(yesterday)

    # Check whether yesterday's schedule extends into today.
    if yesterday_hours and not yesterday_hours.is_closed:

        if yesterday_hours.is_overnight:
            if current_clock < yesterday_hours.closes_at:
                return "open"

    # No schedule available for today.
    if today_hours is None:
        return "unknown"

    # Closed all day today.
    if today_hours.is_closed:
        return "closed"

    opens_at = today_hours.opens_at
    closes_at = today_hours.closes_at

    # Normal opening hours.
    if opens_at < closes_at:
        if opens_at <= current_clock < closes_at:
            return "open"

    # Overnight opening hours.
    else:
        if current_clock >= opens_at:
            return "open"

    return "closed"
