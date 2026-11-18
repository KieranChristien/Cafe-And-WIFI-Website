from flask import Blueprint, flash, redirect, render_template, url_for, jsonify

from web.extensions import db, limiter
from web.forms import CafeAddForm, CafeEditForm, CafeReviewForm
from web.models import Cafe, CafeReview
from web.services.database import commit_session
from web.services.geocoding import AddressNotFound, GeocodingUnavailable, get_directions_url, search_address
from web.utils import format_phone_number

listing = Blueprint('listing', __name__)


@listing.route('/listing/add', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def add():
    form = CafeAddForm()

    if form.validate_on_submit():
        try:
            candidates = search_address(
                address_line_1=form.address_line_1.data,
                city=form.location.data,
                region=form.region.data,
                postal_code=form.postal_code.data,
                country_code=form.country_code.data,
            )

        except AddressNotFound as exc:
            form.address_line_1.errors.append(str(exc))

        except GeocodingUnavailable:
            flash(
                "The address verification service is temporarily unavailable.",
                "error",
            )

        else:
            # Present candidates to the user for confirmation.
            return render_template(
                "listing/confirm_location.html",
                form=form,
                candidates=candidates,
            )

    return render_template(
        "./listing/edit.html",
        website_title="Add Cafe"
    )


@listing.route('/listing/<int:cafe_id>/edit', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def edit(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        flash("Cafe not found.", "error")
        return redirect(url_for("main.home"))

    form = CafeEditForm()

    if form.validate_on_submit():
        updates = {}
        lookup_failed = False

        # -----------------------------------------------------
        # Phone number
        # -----------------------------------------------------

        phone_number = (form.phone_number.data or "").strip() or None

        if phone_number != cafe.phone_number:
            updates["phone_number"] = phone_number

        # -----------------------------------------------------
        # Address verification
        # -----------------------------------------------------
        try:
            candidates = search_address(
                address_line_1=form.address_line_1.data,
                city=form.location.data,
                region=form.region.data,
                postal_code=form.postal_code.data,
                country_code=form.country_code.data,
            )

        except AddressNotFound as exc:
            form.address_line_1.errors.append(str(exc))
            lookup_failed = True

        except GeocodingUnavailable:
            flash(
                "The address verification service is temporarily unavailable.",
                "error",
            )
            lookup_failed = True

        else:
            # -------------------------------------------------
            # Multiple candidates: request user confirmation
            # -------------------------------------------------

            if len(candidates) > 1:
                return jsonify(candidates)

            if not candidates:
                form.address_line_1.errors.append(
                    "No matching building address was found."
                )
                lookup_failed = True
            else:
                result = candidates[0]
                address = result["provider_address"]

                # ---------------------------------------------
                # Build address updates
                # ---------------------------------------------

                updates.update({
                    "location": (
                            address.get("municipalitySubdivision")
                            or address.get("municipality")
                    ),
                    "address_line_1": (
                        f"{address.get('houseNumber', '')} "
                        f"{address.get('street', '')}"
                    ).strip(),
                    "address_line_2": (form.address_line_2.data or "").strip() or None,
                    "postal_code": (
                            address.get("extendedPostalCode")
                            or address.get("postalCode")
                    ),
                    "city": address.get("municipality"),
                    "country": address.get("country"),
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "location_provider": result["provider"],
                    "location_provider_id": result["provider_id"],
                })

        # -----------------------------------------------------
        # Handle address verification failure
        # -----------------------------------------------------

        if lookup_failed:
            return render_template(
                "./listing/edit.html",
                cafe=cafe,
                form=form,
                website_title=cafe.name,
            )

        # -----------------------------------------------------
        # Apply only actual changes
        # -----------------------------------------------------

        changed = {
            key: value
            for key, value in updates.items()
            if getattr(cafe, key) != value
        }

        for key, value in changed.items():
            setattr(cafe, key, value)

        # -----------------------------------------------------
        # Commit transaction
        # -----------------------------------------------------

        if changed and not commit_session(
                success_message="Cafe updated successfully!",
                error_message="Unable to update the cafe. Please try again.",
                integrity_error_message="The submitted cafe information conflicts with existing data.",
                debug_message=f"Failed to update cafe ID {cafe_id}.",
                integrity_debug_message=f"Integrity violation updating cafe ID {cafe_id}.",
        ):
            return redirect(
                url_for("listing.edit", cafe_id=cafe_id)
            )

        return redirect(url_for("listing.view", cafe_id=cafe_id))

    return render_template(
        "./listing/edit.html",
        cafe=cafe,
        form=form,
        website_title=cafe.name,
    )


@listing.route('/listing/<int:cafe_id>', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def view(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        flash('Cafe not found.', 'error')
        return redirect(url_for('main.home'))

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

    phone_number = format_phone_number(cafe.phone_number) if cafe.phone_number is not None else None

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

    return render_template(
        "./listing/view.html",
        cafe=cafe,
        form=form,
        address=address,
        phone_number=phone_number,
        website_title=cafe.name,
    )


@listing.route('/listing/example')
def example():
    return render_template("./listing/example.html")
