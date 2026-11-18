import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import pycountry
import requests

from flask import current_app

TOMTOM_URL = "https://api.tomtom.com/maps/orbis/places/structuredGeocode"
GOOGLE_MAPS_DIR_URL = "https://www.google.com/maps/dir/?api=1"


class GeocodingError(Exception):
    """Base exception for geocoding errors."""


class AddressNotFound(GeocodingError):
    """No suitable address was found."""


class GeocodingUnavailable(GeocodingError):
    """The geocoding service could not be reached."""


def normalise_address(value: object) -> str:
    """Normalise address components for comparison."""
    return " ".join(str(value or "").strip().casefold().split())


def normalise_postal_code(value: object) -> str:
    """Compare postal codes without differences in spaces or punctuation."""
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).casefold()


def normalise_street_name(value: str) -> str:
    """Normalise common UK street abbreviations."""

    value = " ".join(str(value or "").strip().split())

    abbreviations = {
        r"\bRd\.?$": "Road",
        r"\bSt\.?$": "Street",
        r"\bAve\.?$": "Avenue",
        r"\bLn\.?$": "Lane",
        r"\bDr\.?$": "Drive",
        r"\bCres\.?$": "Crescent",
        r"\bCl\.?$": "Close",
        r"\bCt\.?$": "Court",
        r"\bPl\.?$": "Place",
        r"\bSq\.?$": "Square",
        r"\bTer\.?$": "Terrace",
    }

    for pattern, replacement in abbreviations.items():
        value = re.sub(
            pattern,
            replacement,
            value,
            flags=re.IGNORECASE,
        )

    return value


def split_address(address_line_1: str) -> tuple[str, str]:
    """
    Extract a building number and street name from the first address line.

    Examples:
        41 Fitzroy Str  -> 41, Fitzroy Str
        12A Main Road   -> 12A, Main Road
        41-43 Main Road -> 41-43, Main Road
    """
    if not isinstance(address_line_1, str):
        raise AddressNotFound(
            "Please include a building number followed by a street name."
        )

    match = re.fullmatch(
        r"\s*(?P<number>\d+[A-Za-z]?(?:\s*[-/]\s*\d+[A-Za-z]?)?)"
        r"\s+(?P<street>.+?)\s*",
        address_line_1,
    )

    if not match:
        raise AddressNotFound(
            "Please include a building number followed by a street name."
        )

    return match.group("number"), match.group("street")


def search_address(
        address_line_1: str,
        city: str,
        country_code: str,
        region: str | None = None,
        postal_code: str | None = None,
) -> list[dict]:
    """Look up and validate a structured address using TomTom Orbis v2."""
    logger = current_app.logger

    # ------------------------------------------------------------------
    # Validate configuration and input
    # ------------------------------------------------------------------
    if not isinstance(country_code, str) or not country_code.strip():
        raise ValueError("A valid two-letter country code is required.")

    country = pycountry.countries.get(alpha_2=country_code.strip().upper())
    if country is None:
        raise ValueError("Invalid country code.")

    api_key = current_app.config.get("TOMTOM_API_KEY")
    if not isinstance(api_key, str) or not api_key.strip():
        raise RuntimeError("TOMTOM_API_KEY is not configured.")

    if not isinstance(city, str) or not city.strip():
        raise ValueError("A city or locality is required.")

    house_number, street = split_address(address_line_1)
    street = normalise_street_name(street)
    city = city.strip()
    region = region.strip() if isinstance(region, str) else None
    postal_code = postal_code.strip() if isinstance(postal_code, str) else None

    # ------------------------------------------------------------------
    # Structured geocoding parameters (TomTom Orbis API v2)
    # ------------------------------------------------------------------
    params = {
        "countryCodeIso2": country.alpha_2.upper(),
        "houseNumber": house_number,
        "street": street,
        "municipality": city,
        "countrySubdivision": region,
        "postalCode": postal_code,
        "types": "address",
        "maxResults": 10,
    }
    params = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }

    headers = {
        "TomTom-Api-Key": api_key.strip(),
        "TomTom-Api-Version": "2",
        # Ask for the full results object so the diagnostic log can show
        # the returned address fields and the code can validate them.
        "Attributes": "results",
        "Accept": "application/json",
    }

    logger.info(
        "Starting TomTom geocoding: house_number=%r street=%r city=%r "
        "region=%r postal_code=%r country_code=%r",
        house_number,
        street,
        city,
        region,
        postal_code,
        country.alpha_2,
    )
    logger.debug("TomTom request parameters: %s", params)

    # ------------------------------------------------------------------
    # Make API request
    # ------------------------------------------------------------------
    try:
        response = requests.get(
            TOMTOM_URL,
            params=params,
            headers=headers,
            timeout=(3.05, 10),
        )
        response.raise_for_status()

    except requests.HTTPError as exc:
        error_response = exc.response
        status_code = (
            error_response.status_code if error_response is not None else None
        )
        response_body = (
            error_response.text[:2000] if error_response is not None else ""
        )

        # The API key is sent in a header, not in the URL. Never log headers.
        logger.error(
            "TomTom geocoding HTTP error: status=%r url=%r response_body=%r",
            status_code,
            error_response.url if error_response is not None else TOMTOM_URL,
            response_body,
            exc_info=True,
        )

        if status_code in (401, 403):
            message = "The TomTom API key is invalid or does not have access."
        elif status_code == 429:
            message = "TomTom request limit reached. Please try again later."
        elif status_code == 400:
            message = (
                "TomTom rejected the geocoding request. "
                "Check the application logs for the API error details."
            )
        else:
            message = "The address verification service returned an error."

        raise GeocodingUnavailable(message) from exc

    except requests.RequestException as exc:
        logger.exception("TomTom geocoding request failed: %s", exc)
        raise GeocodingUnavailable(
            "Unable to contact the address verification service."
        ) from exc

    logger.info(
        "TomTom geocoding response received: status=%s elapsed_seconds=%.3f",
        response.status_code,
        response.elapsed.total_seconds(),
    )

    # ------------------------------------------------------------------
    # Decode and validate API response
    # ------------------------------------------------------------------
    try:
        payload = response.json()
    except ValueError as exc:
        logger.error(
            "TomTom returned invalid JSON: response_body=%r",
            response.text[:2000],
            exc_info=True,
        )
        raise GeocodingUnavailable(
            "TomTom returned an unreadable response."
        ) from exc

    if not isinstance(payload, dict):
        logger.error("TomTom returned a non-object JSON response: %r", payload)
        raise GeocodingUnavailable(
            "TomTom returned an unexpected response."
        )

    results = payload.get("results")
    if not isinstance(results, list):
        logger.error(
            "TomTom response has no valid 'results' list. Payload keys=%r payload=%r",
            list(payload.keys()),
            payload,
        )
        raise GeocodingUnavailable(
            "TomTom returned an unexpected results structure."
        )

    logger.info("TomTom returned %d geocoding result(s).", len(results))
    if not results:
        logger.warning(
            "TomTom returned zero results for parameters: %s", params
        )

    # ------------------------------------------------------------------
    # Process and validate candidates
    # ------------------------------------------------------------------
    candidates: list[dict] = []
    rejection_counts: dict[str, int] = {}

    def reject(index: int, reason: str, result: object) -> None:
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        logger.info(
            "Discarding TomTom candidate #%d: reason=%s candidate=%r",
            index,
            reason,
            result,
        )

    for index, result in enumerate(results, start=1):
        if not isinstance(result, dict):
            reject(index, "result_is_not_an_object", result)
            continue

        address = result.get("address")
        if not isinstance(address, dict):
            reject(index, "address_is_missing_or_not_an_object", result)
            continue

        # Log the fields used by the validation checks before filtering.
        logger.info(
            "TomTom candidate #%d: type=%r title=%r house_number=%r "
            "street=%r municipality=%r postal_code=%r extended_postal_code=%r "
            "country_code=%r position=%r",
            index,
            result.get("type"),
            result.get("title"),
            address.get("houseNumber"),
            address.get("street"),
            address.get("municipality"),
            address.get("postalCode"),
            address.get("extendedPostalCode"),
            address.get("countryCodeIso2"),
            result.get("position"),
        )

        # Only accept house-number-level address results.
        result_type = result.get("type")
        if result_type != "address":
            reject(index, f"unexpected_result_type:{result_type!r}", result)
            continue

        # Verify country.
        result_country = address.get("countryCodeIso2")
        if normalise_address(result_country) != country.alpha_2.casefold():
            reject(index, "country_code_does_not_match", result)
            continue

        # Verify the exact requested building number.
        result_house_number = address.get("houseNumber")
        if normalise_address(result_house_number) != normalise_address(
                house_number
        ):
            reject(index, "house_number_does_not_match", result)
            continue

        # Verify the exact requested street.
        requested_street = normalise_address(
            normalise_street_name(street)
        )

        result_street = normalise_address(
            normalise_street_name(
                address.get("street", "")
            )
        )

        if requested_street != result_street:
            reject(index, "street_name_does_not_match", result)
            continue

        # TomTom may return only the outward/partial code in postalCode and
        # the full postcode in extendedPostalCode. Accept an exact match in
        # either field, ignoring spaces and punctuation (e.g. SE15 3SN/SE153SN).
        if postal_code:
            requested_postal_code = normalise_postal_code(postal_code)
            result_postal_codes = {
                normalise_postal_code(value)
                for value in (
                    address.get("postalCode"),
                    address.get("extendedPostalCode"),
                )
                if value
            }

            if requested_postal_code not in result_postal_codes:
                reject(
                    index,
                    "postal_code_does_not_match:"
                    f"requested={postal_code!r}, "
                    f"returned={sorted(result_postal_codes)!r}",
                    result,
                )
                continue

        # ------------------------------------------------------------------
        # Extract coordinates. Orbis v2 returns GeoJSON [longitude, latitude].
        # ------------------------------------------------------------------
        position = result.get("position")
        coordinates = (
            position.get("coordinates") if isinstance(position, dict) else None
        )

        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            reject(index, "position_coordinates_missing_or_invalid", result)
            continue

        try:
            longitude = Decimal(str(coordinates[0]))
            latitude = Decimal(str(coordinates[1]))
        except (InvalidOperation, TypeError, ValueError):
            reject(index, "coordinates_are_not_numeric", result)
            continue

        if not longitude.is_finite() or not latitude.is_finite():
            reject(index, "coordinates_are_not_finite", result)
            continue

        if not (
                Decimal("-90") <= latitude <= Decimal("90")
                and Decimal("-180") <= longitude <= Decimal("180")
        ):
            reject(index, "coordinates_are_out_of_range", result)
            continue

        # ------------------------------------------------------------------
        # Normalise address into the application's existing format
        # ------------------------------------------------------------------
        normalised_address = {
            "house_number": result_house_number,
            "road": address.get("street"),
            "city": address.get("municipality"),
            "town": address.get("municipality"),
            "county": address.get("countrySecondarySubdivision"),
            "state": address.get("countrySubdivision"),
            # Prefer the full postcode when TomTom supplies it.
            "postcode": (
                    address.get("extendedPostalCode")
                    or address.get("postalCode")
            ),
            "country": address.get("country"),
            "country_code": country.alpha_2.lower(),
        }

        candidate = {
            "formatted_address": result.get("title"),
            "latitude": latitude,
            "longitude": longitude,
            "address": normalised_address,
            "provider_address": address,
            "provider": "tomtom",
            "provider_id": result.get("id"),
            "category": "address",
            "type": result_type,
        }
        candidates.append(candidate)

        logger.info(
            "Accepted TomTom candidate #%d: title=%r latitude=%s longitude=%s",
            index,
            candidate["formatted_address"],
            latitude,
            longitude,
        )

    # ------------------------------------------------------------------
    # No exact match found
    # ------------------------------------------------------------------
    if not candidates:
        logger.warning(
            "No TomTom candidates passed validation. Rejection counts=%s; "
            "requested house_number=%r street=%r city=%r postal_code=%r country=%r",
            rejection_counts,
            house_number,
            street,
            city,
            postal_code,
            country.alpha_2,
        )
        raise AddressNotFound(
            "No matching building address was found. "
            "Please check the building number, street name and postal code."
        )

    logger.info(
        "TomTom geocoding completed: accepted=%d rejected=%d",
        len(candidates),
        sum(rejection_counts.values()),
    )
    return candidates


def get_directions_url(latitude: str, longitude: str) -> str:
    """Build a Google Maps directions URL for the supplied coordinates."""
    destination = f"{latitude},{longitude}"
    return f"{GOOGLE_MAPS_DIR_URL}&{urlencode({'destination': destination})}"
