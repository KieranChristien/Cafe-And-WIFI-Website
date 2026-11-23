import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
    jsonify,
    request,
)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from web.extensions import db, limiter
from web.forms import CafeAddressForm, CafeEditForm, CafeReviewForm
from web.models import Cafe, CafeOpeningHour, CafePhoto, CafeReview
from web.services.cloudinary_storage import (
    validate_image_file,
    upload_image_file,
    delete_image_file,
)
from web.services.database import commit_session
from web.services.geocoding import (AddressNotFound, GeocodingUnavailable, geocode_rough_address, get_directions_url,
                                    reverse_geocode)
from web.services.overview import sanitize_overview
from web.services.timezone import get_timezone_from_coordinates
from web.utils import format_phone_number

listing = Blueprint('listing', __name__)

MAX_TOTAL_CAFE_PHOTOS = 20
MAX_PHOTO_SIZE_BYTES = 5 * 1024 * 1024

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
        # Validate image selection
        # --------------------------------------------------

        image_file = edit_form.image.data
        has_upload = bool(
            image_file and image_file.filename
        )

        image_url = (
                edit_form.image_url.data or ""
        ).strip()

        # A user must choose one image source.
        if has_upload and image_url:
            flash(
                "Please upload an image or enter an image URL, not both.",
                "error",
            )

            return _render_edit_page(
                cafe,
                edit_form,
                address_form,
            )

        # Verify actual image contents.
        if has_upload:

            image_error = validate_image_file(image_file)

            if image_error:
                flash(image_error, "error")

                return _render_edit_page(
                    cafe,
                    edit_form,
                    address_form,
                )

        # --------------------------------------------------
        # Validate gallery photo changes
        # --------------------------------------------------

        photo_files = [
            photo
            for photo in request.files.getlist("photos")
            if photo and photo.filename
        ]

        # Identify existing photos selected for removal.
        raw_remove_ids = request.form.getlist("remove_photo_ids")

        try:
            remove_photo_ids = {
                int(photo_id)
                for photo_id in raw_remove_ids
            }
        except ValueError:
            flash("Invalid photo selection.", "error")
            return _render_edit_page(cafe, edit_form, address_form)

        existing_photos = {
            photo.id: photo
            for photo in cafe.photos
        }

        # Prevent a user from deleting another café's photos.
        if not remove_photo_ids.issubset(existing_photos.keys()):
            flash("Invalid photo selection.", "error")
            return _render_edit_page(cafe, edit_form, address_form)

        # Calculate the final gallery size.
        final_photo_count = (
                len(existing_photos)
                - len(remove_photo_ids)
                + len(photo_files)
        )

        if final_photo_count > MAX_TOTAL_CAFE_PHOTOS:
            flash(
                f"A café can have a maximum of "
                f"{MAX_TOTAL_CAFE_PHOTOS} photos. "
                f"Remove some existing photos before adding more.",
                "error",
            )
            return _render_edit_page(cafe, edit_form, address_form)

        # Validate each uploaded gallery image.
        for photo_file in photo_files:

            try:
                photo_file.stream.seek(0, 2)
                photo_size = photo_file.stream.tell()
            finally:
                photo_file.stream.seek(0)

            if not 0 < photo_size <= MAX_PHOTO_SIZE_BYTES:
                flash(
                    f"{photo_file.filename} must be 5 MB or smaller.",
                    "error",
                )
                return _render_edit_page(cafe, edit_form, address_form)

            photo_error = validate_image_file(photo_file)

            if photo_error:
                flash(
                    f"{photo_file.filename}: {photo_error}",
                    "error",
                )
                return _render_edit_page(cafe, edit_form, address_form)

        photos_to_remove = [
            existing_photos[photo_id]
            for photo_id in remove_photo_ids
        ]

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
        # Upload cover image and gallery photos
        # --------------------------------------------------

        old_public_id = cafe.img_public_id

        uploaded_image = None
        uploaded_assets = []
        uploaded_photo_records = []

        # Upload the cover image if one was selected.
        if has_upload:

            uploaded_image, upload_error = upload_image_file(
                image_file
            )

            if upload_error:
                flash(upload_error, "error")

                return _render_edit_page(
                    cafe,
                    edit_form,
                    address_form,
                )

            uploaded_assets.append(uploaded_image)

        # Upload each gallery photo.
        for index, photo_file in enumerate(photo_files, start=1):

            uploaded_photo, upload_error = upload_image_file(
                photo_file
            )

            if upload_error:

                # Remove any images already uploaded in this request.
                for uploaded in uploaded_assets:
                    cleanup_error = delete_image_file(
                        uploaded["public_id"]
                    )

                    if cleanup_error:
                        current_app.logger.error(
                            "[Photo cleanup] %s",
                            cleanup_error,
                        )

                flash(
                    f"Gallery photo {index} could not be uploaded: "
                    f"{upload_error}",
                    "error",
                )

                return _render_edit_page(
                    cafe,
                    edit_form,
                    address_form,
                )

            uploaded_assets.append(uploaded_photo)

            uploaded_photo_records.append(
                CafePhoto(
                    img_url=uploaded_photo["secure_url"],
                    img_public_id=uploaded_photo["public_id"],
                    img_asset_id=uploaded_photo["asset_id"],
                )
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
        # Image updates
        # --------------------------------------------------

        if uploaded_image:

            updates.update({
                "img_url": uploaded_image["secure_url"],
                "img_public_id": uploaded_image["public_id"],
                "img_asset_id": uploaded_image["asset_id"],
            })

        elif image_url:

            # External image URL selected instead.
            updates.update({
                "img_url": image_url,
                "img_public_id": None,
                "img_asset_id": None,
            })

        # --------------------------------------------------
        # Apply gallery changes
        # --------------------------------------------------

        for photo in uploaded_photo_records:
            cafe.photos.append(photo)

        for photo in photos_to_remove:
            db.session.delete(photo)

        gallery_changed = bool(
            uploaded_photo_records or photos_to_remove
        )

        removed_photo_public_ids = [
            photo.img_public_id
            for photo in photos_to_remove
            if photo.img_public_id
        ]

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

        if changed or opening_hours_changed or gallery_changed:

            saved = commit_session(
                success_message="Cafe updated successfully!",
                error_message="Unable to update the cafe. Please try again.",
                integrity_error_message=(
                    "The submitted cafe information conflicts "
                    "with existing data."
                ),
                debug_message=f"Failed to update cafe ID {cafe_id}.",
                integrity_debug_message=(
                    f"Integrity violation updating cafe ID {cafe_id}."
                ),
            )

            if not saved:

                # The database transaction failed.
                # Remove all newly uploaded Cloudinary images.
                for uploaded in uploaded_assets:

                    cleanup_error = delete_image_file(
                        uploaded["public_id"]
                    )

                    if cleanup_error:
                        current_app.logger.error(
                            "[Image cleanup] Failed to remove "
                            "uncommitted image: %s",
                            cleanup_error,
                        )

                return _render_edit_page(
                    cafe,
                    edit_form,
                    address_form,
                )

        # --------------------------------------------------
        # Delete removed gallery photos from Cloudinary
        # --------------------------------------------------

        for public_id in removed_photo_public_ids:

            cleanup_error = delete_image_file(public_id)

            if cleanup_error:
                current_app.logger.warning(
                    "[Photo cleanup] Database removal succeeded, "
                    "but Cloudinary deletion failed: %s",
                    cleanup_error,
                )

                flash(
                    "Some removed photos could not be deleted "
                    "from image storage.",
                    "warning",
                )

        # --------------------------------------------------
        # Remove previous image after successful database save
        # --------------------------------------------------

        new_public_id = (
            uploaded_image["public_id"]
            if uploaded_image
            else None if image_url
            else old_public_id
        )

        if (
                old_public_id
                and old_public_id != new_public_id
        ):

            cleanup_error = delete_image_file(old_public_id)

            if cleanup_error:
                current_app.logger.warning(
                    "[Image cleanup] Image was updated, "
                    "but old image could not be deleted: %s",
                    cleanup_error,
                )

                flash(
                    "Your café was updated, but the previous image "
                    "could not be removed from storage.",
                    "warning",
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
