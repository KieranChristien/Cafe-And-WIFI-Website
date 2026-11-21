from datetime import datetime, timezone, timedelta

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from web.models import Cafe
from web.services.clock import get_local_now, get_current_time


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
        current_time = get_current_time()

    # Reject naive datetimes to prevent ambiguous comparisons.
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        return "unknown"

    # Convert to the cafe's local timezone.
    try:
        local_time = current_time.astimezone(
            ZoneInfo(cafe.timezone.__str__())
        )
    except (ZoneInfoNotFoundError, TypeError):
        return "unknown"

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


def _get_opening_interval(cafe: Cafe, day, tz):
    """Return the scheduled opening and closing datetimes for a day."""
    hours = next(
        (entry for entry in cafe.opening_hours
         if entry.weekday == day.weekday()),
        None,
    )

    if hours is None or hours.is_closed:
        return None

    opening = datetime.combine(
        day, hours.opens_at
    ).replace(tzinfo=tz)

    closing_day = (
        day + timedelta(days=1)
        if hours.is_overnight
        else day
    )

    closing = datetime.combine(
        closing_day, hours.closes_at
    ).replace(tzinfo=tz)

    return opening, closing


def get_next_opening_time(
    cafe: Cafe,
    current_time: datetime | None = None,
) -> datetime | None:
    """Return the next scheduled opening datetime."""

    if cafe.is_manually_closed:
        return None

    current_time = current_time or get_current_time()
    local_now = get_local_now(current_time, cafe.timezone.__str__())

    if local_now is None:
        return None

    for offset in range(8):
        day = local_now.date() + timedelta(days=offset)

        interval = _get_opening_interval(
            cafe, day, local_now.tzinfo
        )

        if interval is None:
            continue

        opening, _ = interval

        if opening > local_now:
            return opening

    return None


def get_next_closing_time(
        cafe: Cafe,
        current_time: datetime | None = None,
) -> datetime | None:
    """Return the next scheduled closing datetime."""
    current_time = current_time or get_current_time()
    local_now = get_local_now(current_time, cafe.timezone.__str__())

    if local_now is None:
        return None

    # Include yesterday for overnight sessions already in progress.
    for offset in range(-1, 8):
        day = local_now.date() + timedelta(days=offset)
        interval = _get_opening_interval(
            cafe, day, local_now.tzinfo
        )

        if interval is None:
            continue

        _, closing = interval

        if closing > local_now:
            return closing

    return None
