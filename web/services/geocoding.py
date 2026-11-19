"""TomTom Orbis geocoding helpers for café addresses.

This module deliberately accepts both numbered building addresses and
street-only addresses. A street result is returned as lower-confidence data
so the owner can confirm it rather than being silently treated as a building.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from urllib.parse import urlencode

import pycountry
import requests
from flask import current_app

TOMTOM_GEOCODE_URL = "https://api.tomtom.com/maps/orbis/places/geocode"
GOOGLE_MAPS_DIR_URL = "https://www.google.com/maps/dir/?api=1"

REQUEST_TIMEOUT = (3.05, 10)
MAX_RESULTS = 10


class GeocodingError(Exception):
    """Base exception for address lookup errors."""


class AddressNotFound(GeocodingError):
    """No usable address candidates were returned."""


class GeocodingUnavailable(GeocodingError):
    """The geocoding provider could not be reached or returned an error."""


# Match a leading house number, including common ranges such as 160-164
# and alphanumeric numbers such as 12A. The number is optional.
_HOUSE_NUMBER_PREFIX = re.compile(
    r"^\s*(?P<number>\d+[A-Za-z]?(?:\s*[-/]\s*\d+[A-Za-z]?)?)"
    r"\s+(?P<street>[^,]+)",
    flags=re.IGNORECASE,
)
_HOUSE_NUMBER_SINGLE = re.compile(r"^\s*(\d+)\s*([A-Za-z]?)\s*$")
_HOUSE_NUMBER_RANGE = re.compile(
    r"^\s*(\d+\s*[A-Za-z]?)\s*[-/]\s*(\d+\s*[A-Za-z]?)\s*$"
)

_STREET_SUFFIXES = {
    "rd": "road",
    "st": "street",
    "ave": "avenue",
    "ln": "lane",
    "dr": "drive",
    "cres": "crescent",
    "cl": "close",
    "ct": "court",
    "pl": "place",
    "sq": "square",
    "ter": "terrace",
}

TOMTOM_REVERSE_URL = (
    "https://api.tomtom.com/maps/orbis/places/reverseGeocode"
)


def _tomtom_headers() -> dict:
    api_key = current_app.config.get("TOMTOM_API_KEY")

    if not isinstance(api_key, str) or not api_key.strip():
        raise GeocodingUnavailable(
            "The location service is not configured."
        )

    return {
        "TomTom-Api-Key": api_key.strip(),
        "TomTom-Api-Version": "2",
        "Attributes": "results",
        "Accept": "application/json",
    }


def _tomtom_results(
        url: str,
        params: dict,
        operation: str,
) -> list:
    """Request and validate a TomTom results response."""

    try:
        response = requests.get(
            url,
            params=params,
            headers=_tomtom_headers(),
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code
            if exc.response is not None
            else None
        )

        current_app.logger.warning(
            "TomTom %s returned HTTP status %s.",
            operation,
            status_code,
        )

        raise GeocodingUnavailable(
            "The location service returned an error."
        ) from exc

    except requests.RequestException as exc:
        current_app.logger.exception(
            "TomTom %s request failed.",
            operation,
        )

        raise GeocodingUnavailable(
            "Unable to contact the location service."
        ) from exc

    try:
        payload = response.json()

    except ValueError as exc:
        raise GeocodingUnavailable(
            "The location service returned invalid JSON."
        ) from exc

    if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("results"), list)
    ):
        raise GeocodingUnavailable(
            "The location service returned an unexpected response."
        )

    return payload["results"]


def _coordinates_from_result(result: object):
    """Extract validated coordinates from a TomTom result."""

    if not isinstance(result, dict):
        return None

    position = result.get("position")

    if not isinstance(position, dict):
        return None

    coordinates = position.get("coordinates")

    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        return None

    try:
        longitude = Decimal(str(coordinates[0]))
        latitude = Decimal(str(coordinates[1]))

    except (InvalidOperation, TypeError, ValueError):
        return None

    if not latitude.is_finite() or not longitude.is_finite():
        return None

    if not (
            Decimal("-90") <= latitude <= Decimal("90")
            and Decimal("-180") <= longitude <= Decimal("180")
    ):
        return None

    return latitude, longitude


def _provider_text(
        value: object,
        *,
        max_length: int,
        field_name: str,
) -> str | None:
    """Clean and validate provider-supplied address text."""

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if len(value) > max_length:
        raise GeocodingUnavailable(
            f"The location service returned an invalid {field_name}."
        )

    return value


def normalise_address(value: object) -> str:
    """Return a case-insensitive, punctuation-insensitive comparison value."""
    value = str(value or "").casefold().strip()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def normalise_postal_code(value: object) -> str:
    """Remove spaces and punctuation from a postcode for comparison."""
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).casefold()


def normalise_street_name(value: object) -> str:
    """Normalise common street suffix abbreviations before comparison."""
    words = str(value or "").strip().split()
    if not words:
        return ""

    final_word = re.sub(r"[.]$", "", words[-1]).casefold()
    if final_word in _STREET_SUFFIXES:
        words[-1] = _STREET_SUFFIXES[final_word]

    return normalise_address(" ".join(words))


def split_address(address_line_1: str) -> tuple[str | None, str]:
    """Extract an optional leading building number and street name.

    Examples:
        '160-164 Goswell Rd.' -> ('160-164', 'Goswell Rd.')
        '12A Main Road'       -> ('12A', 'Main Road')
        'Montague Close'      -> (None, 'Montague Close')

    Only the first comma-delimited segment is used for comparison. The full
    submitted line is still sent to TomTom, so a user can paste a full address.
    """
    if not isinstance(address_line_1, str) or not address_line_1.strip():
        raise AddressNotFound("Please enter a street address or street name.")

    first_segment = address_line_1.split(",", 1)[0].strip()
    match = _HOUSE_NUMBER_PREFIX.match(first_segment)
    if match:
        return match.group("number").strip(), match.group("street").strip()

    return None, first_segment


def _house_number_key(value: str) -> tuple[int, str] | None:
    match = _HOUSE_NUMBER_SINGLE.fullmatch(str(value or ""))
    if not match:
        return None
    return int(match.group(1)), match.group(2).casefold()


def _house_number_range(value: str) -> tuple[str, str] | None:
    match = _HOUSE_NUMBER_RANGE.fullmatch(str(value or ""))
    if not match:
        return None
    start = re.sub(r"\s+", "", match.group(1))
    end = re.sub(r"\s+", "", match.group(2))
    return start, end


def house_number_matches(requested: str, returned: str) -> bool:
    """Check a returned number against an exact number or requested range."""
    if normalise_address(requested) == normalise_address(returned):
        return True

    requested_range = _house_number_range(requested)
    if requested_range is None:
        return False

    requested_start = _house_number_key(requested_range[0])
    requested_end = _house_number_key(requested_range[1])
    if requested_start is None or requested_end is None:
        return False

    returned_number = _house_number_key(returned)
    if returned_number is not None:
        return requested_start <= returned_number <= requested_end

    returned_range = _house_number_range(returned)
    if returned_range is None:
        return False

    returned_start = _house_number_key(returned_range[0])
    returned_end = _house_number_key(returned_range[1])
    if returned_start is None or returned_end is None:
        return False

    return requested_start <= returned_start and returned_end <= requested_end


def _street_similarity(left: str, right: str) -> float:
    left_normalised = normalise_street_name(left)
    right_normalised = normalise_street_name(right)
    if not left_normalised or not right_normalised:
        return 1.0
    return SequenceMatcher(None, left_normalised, right_normalised).ratio()


def _postcode_quality(requested: str | None, returned_values: list[object]) -> str:
    """Classify postcode evidence without rejecting partial provider values."""
    requested_normalised = normalise_postal_code(requested)
    if not requested_normalised:
        return "not_supplied"

    returned = {
        normalise_postal_code(value)
        for value in returned_values
        if value
    }
    if not returned:
        return "not_returned"
    if requested_normalised in returned:
        return "exact"
    if any(
            requested_normalised.startswith(value) or value.startswith(requested_normalised)
            for value in returned
    ):
        return "partial"
    return "different"


def _country_from_code(country_code: str):
    if not isinstance(country_code, str) or not country_code.strip():
        raise ValueError("A valid two-letter country code is required.")

    country = pycountry.countries.get(alpha_2=country_code.strip().upper())
    if country is None:
        raise ValueError("Invalid country code.")
    return country


def _build_query(
        address_line_1: str,
        city: str,
        country_name: str,
        region: str | None,
        postal_code: str | None,
) -> str:
    """Build a free-form query and avoid adding identical components twice."""
    parts = [address_line_1, city, region, postal_code, country_name]
    query_parts: list[str] = []
    seen: set[str] = set()

    for part in parts:
        if not isinstance(part, str) or not part.strip():
            continue
        cleaned = " ".join(part.strip().split())
        comparison = normalise_address(cleaned)
        if comparison and comparison not in seen:
            query_parts.append(cleaned)
            seen.add(comparison)

    return ", ".join(query_parts)


def geocode_rough_address(query: str) -> dict:
    """Find an approximate location for a free-form address."""

    if not isinstance(query, str) or not query.strip():
        raise AddressNotFound("Please enter an address.")

    results = _tomtom_results(
        TOMTOM_GEOCODE_URL,
        {
            "query": query.strip(),
            "maxResults": 5,
        },
        "approximate geocoding",
    )

    if not results:
        raise AddressNotFound(
            "No approximate location could be found."
        )

    for result in results:
        coordinates = _coordinates_from_result(result)

        if coordinates is None:
            continue

        latitude, longitude = coordinates

        label = (
            result.get("title")
            if isinstance(result, dict)
            else None
        )

        return {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "label": label if isinstance(label, str) else None,
        }

    raise GeocodingUnavailable(
        "The location service returned no usable coordinates."
    )


def reverse_geocode(latitude: Decimal, longitude: Decimal) -> dict:
    """Convert selected coordinates into a validated structured address."""

    results = _tomtom_results(
        TOMTOM_REVERSE_URL,
        {
            "position": f"{longitude},{latitude}",
            "radiusInMeters": 100,
        },
        "reverse geocoding",
    )

    if not results:
        raise AddressNotFound(
            "No address could be found at the selected location."
        )

    result = next(
        (
            item
            for item in results
            if isinstance(item, dict)
               and item.get("type") == "address"
        ),
        None,
    )

    if result is None:
        raise AddressNotFound(
            "No building-level address was found. "
            "Please move the marker closer to the café."
        )

    provider_address = result.get("address")

    if not isinstance(provider_address, dict):
        raise GeocodingUnavailable(
            "The location service returned an invalid address."
        )

    # Required locality. Cafe.location is NOT NULL in the database.
    location = (
            _provider_text(
                provider_address.get("municipalitySubdivision"),
                max_length=250,
                field_name="locality",
            )
            or _provider_text(
        provider_address.get("municipality"),
        max_length=250,
        field_name="locality",
    )
    )

    if not location:
        raise AddressNotFound(
            "The selected location does not have a recognised locality."
        )

    # Required country.
    country = _provider_text(
        provider_address.get("country"),
        max_length=100,
        field_name="country",
    )

    if not country:
        raise AddressNotFound(
            "The selected location has no identifiable country."
        )

    country_code = _provider_text(
        provider_address.get("countryCodeIso2"),
        max_length=2,
        field_name="country code",
    )

    if not country_code or not re.fullmatch(
            r"[A-Za-z]{2}",
            country_code,
    ):
        raise AddressNotFound(
            "The selected location has no valid country code."
        )

    house_number = _provider_text(
        provider_address.get("houseNumber"),
        max_length=50,
        field_name="house number",
    )

    street = _provider_text(
        provider_address.get("street"),
        max_length=200,
        field_name="street",
    )

    address_line_1 = " ".join(
        part
        for part in (house_number, street)
        if part
    ) or None

    if address_line_1 and len(address_line_1) > 250:
        raise GeocodingUnavailable(
            "The returned street address is too long."
        )

    postal_code = _provider_text(
        (
                provider_address.get("extendedPostalCode")
                or provider_address.get("postalCode")
        ),
        max_length=20,
        field_name="postal code",
    )

    city = _provider_text(
        provider_address.get("municipality"),
        max_length=250,
        field_name="city",
    )

    region = _provider_text(
        provider_address.get("countrySubdivision"),
        max_length=250,
        field_name="region",
    )

    provider_id = _provider_text(
        result.get("id"),
        max_length=255,
        field_name="provider ID",
    )

    return {
        "formatted_address": (
            result.get("title")
            if isinstance(result.get("title"), str)
            else None
        ),
        "address_line_1": address_line_1,
        "address_line_2": None,
        "location": location,
        "postal_code": postal_code,
        "city": city,
        "region": region,
        "country": country,
        "country_code": country_code,
        "latitude": latitude,
        "longitude": longitude,
        "provider": "tomtom",
        "provider_id": provider_id,
    }


def search_address(
        address_line_1: str,
        city: str,
        country_code: str,
        region: str | None = None,
        postal_code: str | None = None,
) -> list[dict]:
    """Search TomTom for building- and street-level candidates.

    ``address_line_1`` may contain a building number, a number range, a street
    name only, or a complete pasted address. ``city`` and ``country_code`` are
    still required to constrain the search.
    """
    logger = current_app.logger
    country = _country_from_code(country_code)

    api_key = current_app.config.get("TOMTOM_API_KEY")
    if not isinstance(api_key, str) or not api_key.strip():
        raise RuntimeError("TOMTOM_API_KEY is not configured.")

    if not isinstance(city, str) or not city.strip():
        raise ValueError("A city or locality is required.")

    if not isinstance(address_line_1, str) or not address_line_1.strip():
        raise AddressNotFound("Please enter a street address or street name.")

    city = city.strip()
    region = region.strip() if isinstance(region, str) and region.strip() else None
    postal_code = (
        postal_code.strip()
        if isinstance(postal_code, str) and postal_code.strip()
        else None
    )

    requested_house_number, requested_street = split_address(address_line_1)
    query = _build_query(
        address_line_1=address_line_1.strip(),
        city=city,
        region=region,
        postal_code=postal_code,
        country_name=country.name,
    )

    params = {
        "query": query,
        "countryCodesIso2": country.alpha_2,
        # Orbis v2 supports both address and street results. Street results
        # are necessary for addresses such as "Montague Close".
        "types": "address,street",
        "maxResults": MAX_RESULTS,
    }
    headers = {
        "TomTom-Api-Key": api_key.strip(),
        "TomTom-Api-Version": "2",
        "Attributes": "results",
        "Accept": "application/json",
    }

    logger.info(
        "Starting TomTom geocoding: query=%r country_code=%s",
        query,
        country.alpha_2,
    )

    try:
        response = requests.get(
            TOMTOM_GEOCODE_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        error_response = exc.response
        status_code = error_response.status_code if error_response is not None else None
        response_body = error_response.text[:1500] if error_response is not None else ""
        logger.error(
            "TomTom geocoding HTTP error: status=%r body=%r",
            status_code,
            response_body,
            exc_info=True,
        )

        if status_code in (401, 403):
            message = "The TomTom API key is invalid or does not have access to geocoding."
        elif status_code == 429:
            message = "The TomTom request limit has been reached. Please try again later."
        elif status_code == 400:
            message = "TomTom rejected the geocoding request. Check the application logs."
        else:
            message = "The address verification service returned an error."
        raise GeocodingUnavailable(message) from exc
    except requests.RequestException as exc:
        logger.exception("TomTom geocoding request failed.")
        raise GeocodingUnavailable(
            "Unable to contact the address verification service."
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        logger.error("TomTom returned invalid JSON: %r", response.text[:1500])
        raise GeocodingUnavailable(
            "TomTom returned an unreadable response."
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        logger.error("Unexpected TomTom response structure: %r", payload)
        raise GeocodingUnavailable(
            "TomTom returned an unexpected results structure."
        )

    candidates: list[dict] = []
    rejection_counts: dict[str, int] = {}
    seen_positions: set[tuple[str, str]] = set()

    def reject(reason: str) -> None:
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    for index, result in enumerate(payload["results"], start=1):
        if not isinstance(result, dict):
            reject("result_not_object")
            continue

        result_type = result.get("type")
        if result_type not in {"address", "street"}:
            reject(f"unsupported_type:{result_type!r}")
            continue

        provider_address = result.get("address")
        if not isinstance(provider_address, dict):
            reject("address_missing")
            continue

        result_country = provider_address.get("countryCodeIso2")
        if result_country and str(result_country).casefold() != country.alpha_2.casefold():
            reject("country_mismatch")
            continue

        returned_street = provider_address.get("street") or ""
        if returned_street and requested_street:
            similarity = _street_similarity(requested_street, returned_street)
            # Tolerate punctuation and common suffix variations, but don't
            # present a clearly different street as a possible match.
            if similarity < 0.72:
                reject("street_mismatch")
                continue
        else:
            similarity = 1.0

        returned_house_number = provider_address.get("houseNumber")
        if (
                requested_house_number
                and result_type == "address"
                and returned_house_number
                and not house_number_matches(requested_house_number, str(returned_house_number))
        ):
            reject("house_number_mismatch")
            continue

        postcode_values = [
            provider_address.get("postalCode"),
            provider_address.get("extendedPostalCode"),
        ]
        postcode_quality = _postcode_quality(postal_code, postcode_values)

        position = result.get("position")
        coordinates = position.get("coordinates") if isinstance(position, dict) else None
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            reject("coordinates_missing")
            continue

        try:
            longitude = Decimal(str(coordinates[0]))
            latitude = Decimal(str(coordinates[1]))
        except (InvalidOperation, TypeError, ValueError):
            reject("coordinates_not_numeric")
            continue

        if not longitude.is_finite() or not latitude.is_finite():
            reject("coordinates_not_finite")
            continue
        if not (
                Decimal("-180") <= longitude <= Decimal("180")
                and Decimal("-90") <= latitude <= Decimal("90")
        ):
            reject("coordinates_out_of_range")
            continue

        position_key = (str(latitude.quantize(Decimal("0.000001"))),
                        str(longitude.quantize(Decimal("0.000001"))))
        if position_key in seen_positions:
            reject("duplicate_position")
            continue
        seen_positions.add(position_key)

        # A numbered address is high confidence when the user supplied a
        # number and TomTom returned a matching number. A street result, or
        # an address with no returned building number, is explicitly marked
        # lower confidence for the owner's confirmation screen.
        exact_number_match = bool(
            requested_house_number
            and returned_house_number
            and house_number_matches(requested_house_number, str(returned_house_number))
        )
        precision = (
            "building"
            if result_type == "address" and (not requested_house_number or exact_number_match)
            else "street"
        )

        normalised_address = {
            "house_number": returned_house_number,
            "road": provider_address.get("street") or requested_street,
            "city": provider_address.get("municipality") or city,
            "town": provider_address.get("municipality"),
            "municipality_subdivision": provider_address.get("municipalitySubdivision"),
            "county": provider_address.get("countrySecondarySubdivision"),
            "state": provider_address.get("countrySubdivision"),
            "postcode": (
                    provider_address.get("extendedPostalCode")
                    or provider_address.get("postalCode")
                    or postal_code
            ),
            "country": provider_address.get("country") or country.name,
            "country_code": country.alpha_2.lower(),
        }

        candidates.append({
            "formatted_address": result.get("title") or ", ".join(
                value for value in (
                    normalised_address["house_number"],
                    normalised_address["road"],
                    normalised_address["city"],
                    normalised_address["postcode"],
                    normalised_address["country"],
                ) if value
            ),
            "latitude": latitude,
            "longitude": longitude,
            "address": normalised_address,
            "provider_address": provider_address,
            "provider": "tomtom",
            "provider_id": result.get("id"),
            "category": "address" if result_type == "address" else "street",
            "type": result_type,
            "precision": precision,
            "postcode_quality": postcode_quality,
            "street_similarity": similarity,
            "exact_house_number_match": exact_number_match,
        })

    # Prefer numbered addresses and exact postcode matches, while retaining
    # street-level fallbacks when no building-level result exists.
    candidates.sort(key=lambda item: (
        0 if item["precision"] == "building" else 1,
        0 if item["postcode_quality"] == "exact" else 1,
        0 if item["exact_house_number_match"] else 1,
        -item["street_similarity"],
    ))

    logger.info(
        "TomTom geocoding completed: accepted=%d rejected=%d rejection_counts=%s",
        len(candidates),
        sum(rejection_counts.values()),
        rejection_counts,
    )

    if not candidates:
        raise AddressNotFound(
            "No suitable location was found. Check the street, locality, postcode and country."
        )

    return candidates


def get_directions_url(latitude: str | Decimal, longitude: str | Decimal) -> str:
    """Build a Google Maps directions URL from latitude/longitude."""
    destination = f"{latitude},{longitude}"
    return f"{GOOGLE_MAPS_DIR_URL}&{urlencode({'destination': destination})}"
