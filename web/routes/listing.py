import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import Blueprint, flash, redirect, render_template, url_for, jsonify, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from web.extensions import db, limiter
from web.forms import CafeAddressForm, CafeEditForm, CafeReviewForm
from web.models import Cafe, CafeOpeningHour, CafeReview
from web.services.database import commit_session
from web.services.geocoding import (AddressNotFound, GeocodingUnavailable, geocode_rough_address, get_directions_url,
                                    reverse_geocode)
from web.services.overview import sanitize_overview
from web.services.timezone import get_timezone_from_coordinates
from web.utils import format_phone_number

listing = Blueprint('listing', __name__)

_COORDINATE_PATTERN = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\Z"
)

COORDINATE_PRECISION = Decimal("0.0000001")


def parse_coordinate(
        raw_value: str | None,
        *,
        minimum: Decimal,
        maximum: Decimal,
) -> Decimal:
    """Validate and normalise a coordinate to seven decimal places."""

    if not isinstance(raw_value, str):
        raise ValueError("Coordinate is missing.")

    raw_value = raw_value.strip()

    if (
            not raw_value
            or len(raw_value) > 32
            or not _COORDINATE_PATTERN.fullmatch(raw_value)
    ):
        raise ValueError("Invalid coordinate format.")

    try:
        value = Decimal(raw_value)

    except InvalidOperation as exc:
        raise ValueError("Invalid coordinate.") from exc

    if not value.is_finite():
        raise ValueError("Coordinate must be finite.")

    if not minimum <= value <= maximum:
        raise ValueError("Coordinate is outside its permitted range.")

    try:
        return value.quantize(
            COORDINATE_PRECISION,
            rounding=ROUND_HALF_UP,
        )

    except InvalidOperation as exc:
        raise ValueError("Unable to normalise coordinate.") from exc


def _render_edit_page(
        cafe: Cafe,
        edit_form: CafeEditForm,
        address_form: CafeAddressForm,
):
    """Re-render the edit page while preserving the submitted map state."""

    if request.method == "POST":
        selected_address_query = (
            request.form.get("address_query", "").strip()[:300]
        )

        # Recover the selected marker coordinates.
        try:
            selected_latitude = parse_coordinate(
                request.form.get("latitude"),
                minimum=Decimal("-90"),
                maximum=Decimal("90"),
            )

            selected_longitude = parse_coordinate(
                request.form.get("longitude"),
                minimum=Decimal("-180"),
                maximum=Decimal("180"),
            )

        except ValueError:
            selected_latitude = None
            selected_longitude = None

        # Recover the map viewport, if it was submitted.
        try:
            map_center_latitude = parse_coordinate(
                request.form.get("map_center_latitude"),
                minimum=Decimal("-90"),
                maximum=Decimal("90"),
            )

            map_center_longitude = parse_coordinate(
                request.form.get("map_center_longitude"),
                minimum=Decimal("-180"),
                maximum=Decimal("180"),
            )

        except ValueError:
            map_center_latitude = selected_latitude
            map_center_longitude = selected_longitude

        zoom_value = request.form.get("map_zoom", "")

        if re.fullmatch(r"\d{1,2}", zoom_value):
            map_zoom = int(zoom_value)
            if not 0 <= map_zoom <= 19:
                map_zoom = 18
        else:
            map_zoom = 18

    else:
        # On the initial GET, use the café's currently saved coordinates.
        selected_address_query = ""

        selected_latitude = cafe.latitude
        selected_longitude = cafe.longitude

        map_center_latitude = cafe.latitude
        map_center_longitude = cafe.longitude

        map_zoom = 18

    # Never restore a viewport without a valid marker position.
    if selected_latitude is None or selected_longitude is None:
        map_center_latitude = None
        map_center_longitude = None

    elif map_center_latitude is None or map_center_longitude is None:
        map_center_latitude = selected_latitude
        map_center_longitude = selected_longitude

    return render_template(
        "./listing/edit.html",
        cafe=cafe,
        edit_form=edit_form,
        address_form=address_form,
        website_title=cafe.name,

        overview_html=sanitize_overview(edit_form.overview.data),

        selected_address_query=selected_address_query,
        selected_latitude=selected_latitude,
        selected_longitude=selected_longitude,

        map_center_latitude=map_center_latitude,
        map_center_longitude=map_center_longitude,
        map_zoom=map_zoom,
    )


@listing.route('/listing/add', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def add():
    return render_template(
        "./listing/edit.html",
        website_title="Add Cafe"
    )


@listing.route(
    '/listing/<int:cafe_id>/address-preview',
    methods=['POST'],
)
@limiter.limit("10 per minute", methods=["POST"])
def address_preview(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        return jsonify({
            "error": "Cafe not found."
        }), 404

    form = CafeAddressForm()

    if not form.validate_on_submit():
        return jsonify({
            "error": "Please enter a valid address.",
            "errors": form.errors,
        }), 400

    try:
        location = geocode_rough_address(
            form.address.data
        )

    except AddressNotFound as exc:
        return jsonify({
            "error": str(exc)
        }), 404

    except GeocodingUnavailable:
        return jsonify({
            "error": "The location service is unavailable."
        }), 503

    return jsonify(location)


@listing.route(
    "/listing/timezone-preview",
    methods=["POST"],
)
@limiter.limit("30 per minute", methods=["POST"])
def timezone_preview():
    """Determine the time zone for the submitted coordinates."""

    try:
        latitude = parse_coordinate(
            request.form.get("latitude"),
            minimum=Decimal("-90"),
            maximum=Decimal("90"),
        )

        longitude = parse_coordinate(
            request.form.get("longitude"),
            minimum=Decimal("-180"),
            maximum=Decimal("180"),
        )

    except ValueError:
        return jsonify({
            "error": "Please provide valid coordinates.",
        }), 400

    timezone_name = get_timezone_from_coordinates(
        latitude=float(latitude),
        longitude=float(longitude),
    )

    if timezone_name is None:
        return jsonify({
            "error": "Could not determine the time zone for this location.",
        }), 422

    return jsonify({
        "timezone": timezone_name,
    })


@listing.route('/listing/<int:cafe_id>/edit', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def edit(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        flash("Cafe not found.", "error")
        return redirect(url_for("main.home"))

    edit_form = CafeEditForm(obj=cafe)
    address_form = CafeAddressForm()

    if edit_form.validate_on_submit():

        # --------------------------------------------------
        # Validate selected coordinates
        # --------------------------------------------------

        try:
            latitude = parse_coordinate(
                request.form.get("latitude"),
                minimum=Decimal("-90"),
                maximum=Decimal("90"),
            )

            longitude = parse_coordinate(
                request.form.get("longitude"),
                minimum=Decimal("-180"),
                maximum=Decimal("180"),
            )

        except ValueError:
            flash(
                "Please select a valid café location on the map.",
                "error",
            )

            return render_template(
                "./listing/edit.html",
                cafe=cafe,
                edit_form=edit_form,
                address_form=address_form,
                website_title=cafe.name,
            )

        # --------------------------------------------------
        # Reverse geocode selected position
        # --------------------------------------------------

        try:

            address = reverse_geocode(
                latitude=latitude,
                longitude=longitude,
            )

        except AddressNotFound as exc:

            flash(str(exc), "error")

            return _render_edit_page(
                cafe,
                edit_form,
                address_form,
            )

        except GeocodingUnavailable:

            flash(
                "The address verification service is "
                "temporarily unavailable.",
                "error",
            )

            return _render_edit_page(
                cafe,
                edit_form,
                address_form,
            )

        # --------------------------------------------------
        # Build database updates
        # --------------------------------------------------

        updates = {

            # General café information
            "name": (edit_form.name.data or "").strip() or None,
            "overview": sanitize_overview(edit_form.overview.data),
            "phone_number": (edit_form.phone_number.data or "").strip() or None,

            # Address
            "address_line_1": address["address_line_1"],
            "address_line_2": address["address_line_2"],
            "location": address["location"],
            "postal_code": address["postal_code"],
            "city": address["city"],
            "country": address["country"],

            # Coordinates
            "latitude": latitude,
            "longitude": longitude,

            "timezone": (edit_form.timezone.data or "").strip() or None,

            # Geocoding metadata
            "location_provider": address["provider"],
            "location_provider_id": address["provider_id"],
        }

        # --------------------------------------------------
        # Build opening-hours updates
        # --------------------------------------------------

        hours_by_weekday = {
            hour.weekday: hour
            for hour in cafe.opening_hours
        }

        opening_hours_changed = False

        for weekday, entry in enumerate(edit_form.opening_hours.entries):

            day_form = entry.form

            # Closed days have no opening or closing times.
            opens_at = None if day_form.is_closed.data else day_form.opens_at.data
            closes_at = None if day_form.is_closed.data else day_form.closes_at.data

            existing_hours = hours_by_weekday.get(weekday)

            if existing_hours is None:

                # Create a missing weekday record.
                existing_hours = CafeOpeningHour(
                    weekday=weekday,
                    opens_at=opens_at,
                    closes_at=closes_at,
                )

                cafe.opening_hours.append(existing_hours)

                opening_hours_changed = True

            elif (
                    existing_hours.opens_at != opens_at
                    or existing_hours.closes_at != closes_at
            ):

                existing_hours.opens_at = opens_at
                existing_hours.closes_at = closes_at

                opening_hours_changed = True

        # --------------------------------------------------
        # Apply only actual changes
        # --------------------------------------------------

        changed = {
            key: value
            for key, value in updates.items()
            if getattr(cafe, key) != value
        }

        for key, value in changed.items():
            setattr(cafe, key, value)

        if changed or opening_hours_changed:

            if not commit_session(
                    success_message="Cafe updated successfully!",
                    error_message="Unable to update the cafe. Please try again.",
                    integrity_error_message="The submitted cafe information conflicts with existing data.",
                    debug_message=f"Failed to update cafe ID {cafe_id}.",
                    integrity_debug_message=f"Integrity violation updating cafe ID {cafe_id}.",
            ):
                return _render_edit_page(
                    cafe,
                    edit_form,
                    address_form,
                )

        return redirect(
            url_for("listing.view", cafe_id=cafe_id)
        )

    # ------------------------------------------------------
    # GET request
    # ------------------------------------------------------

    return _render_edit_page(
        cafe,
        edit_form,
        address_form,
    )


@listing.route('/listing/<int:cafe_id>', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def view(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        flash('Cafe not found.', 'error')
        return redirect(url_for('main.home'))

    overview_html = sanitize_overview(cafe.overview)
    phone_number = format_phone_number(cafe.phone_number) if cafe.phone_number is not None else None

    address = {
        "line1": (
            f"{cafe.address_line_1}"
            + (f", {cafe.address_line_2}" if cafe.address_line_2 is not None else "")
            if cafe.location_provider is not None
            else "No Address"
        ),
        "line2": f"{cafe.postal_code} {cafe.city}, {cafe.country}" if cafe.location_provider is not None else "",
        "directions": get_directions_url(cafe.latitude, cafe.longitude) if cafe.location_provider is not None else "#",
    }

    form = CafeReviewForm()

    if form.validate_on_submit():
        review = CafeReview(
            name=form.name.data,
            body=form.body.data,
            rating=form.rating.data,
        )

        cafe.add_review(review)

        if not commit_session(
                success_message="Your review has been posted!",
                error_message="Unable to post your review. Please try again.",
                integrity_error_message=(
                        "Unable to post your review because the submitted information "
                        "conflicts with database constraints."
                ),
                debug_message=f"Failed to save review for cafe {cafe_id}.",
                integrity_debug_message=(
                        f"Integrity violation saving review for cafe {cafe_id}."
                ),
        ):
            return render_template(
                "./listing/view.html",
                cafe=cafe,
                form=form,
                website_title=cafe.name,
            )

        return redirect(
            url_for("listing.view", cafe_id=cafe_id),
            303,
        )

    today_weekday = None

    if cafe.timezone:
        try:
            today_weekday = datetime.now(ZoneInfo(cafe.timezone)).weekday()
        except (ZoneInfoNotFoundError, ValueError):
            pass

    return render_template(
        "./listing/view.html",
        cafe=cafe,
        form=form,
        overview_html=overview_html,
        phone_number=phone_number,
        address=address,
        today_weekday=today_weekday,
        website_title=cafe.name,
    )


@listing.route('/listing/example')
def example():
    return render_template("./listing/example.html")
