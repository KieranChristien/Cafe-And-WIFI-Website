from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from timezonefinder import TimezoneFinder

_timezone_finder = TimezoneFinder(in_memory=True)


def get_timezone_from_coordinates(
        latitude: float,
        longitude: float,
) -> str | None:
    """Return the IANA time zone for a geographical location."""

    if not -90 <= latitude <= 90:
        raise ValueError("Invalid latitude.")

    if not -180 <= longitude <= 180:
        raise ValueError("Invalid longitude.")

    timezone_name = _timezone_finder.timezone_at(
        lat=latitude,
        lng=longitude,
    )

    if timezone_name is None:
        return None

    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None

    return timezone_name
