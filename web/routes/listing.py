from flask import Blueprint, flash, redirect, render_template, url_for, current_app
from sqlalchemy.exc import IntegrityError

from web.extensions import db, limiter
from web.forms import CafeReviewForm
from web.models import Cafe, CafeReview

listing = Blueprint('listing', __name__)


@listing.route('/listing/<int:cafe_id>', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def view(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        flash('Cafe not found.', 'error')
        return redirect(url_for('main.home'))

    form = CafeReviewForm()

    if form.validate_on_submit():
        review = CafeReview(
            name=form.name.data.strip(),
            body=form.body.data.strip(),
            rating=form.rating.data,
        )

        cafe.add_review(review)

        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()

            current_app.logger.exception(
                "Failed to save review for cafe %s.",
                cafe_id,
            )

            flash("Unable to post your review. Please try again.", "error")

            return redirect(
                url_for('listing.view', cafe_id=cafe_id),
                303,
            )

        flash("Your review has been posted!", "success")

        return redirect(
            url_for('listing.view', cafe_id=cafe_id),
            303,
        )

    return render_template(
        "listing.html",
        cafe=cafe,
        form=form,
        website_title=cafe.name
    )


@listing.route('/listing/example')
def example():
    cafe = Cafe(
        name="Mokka Bar",
        map_url="https://maps.app.goo.gl/rWAVb17SvGTyhz2k6",
        img_url="https://lh3.googleusercontent.com/gps-cs-s/ANWiy9R30tSeGRsZ1HeUlNK5ayOvL6bfrLTI6xRzDeJoL3yhkYpnKRRoOnlR-AaLa-9hEkYcm9xcIoqCsYSTnsc9tchZITP0k4St9gmKaqOunNi4EVn4G2i_EGKm-p316k8TZGdEiVgo=s1360-w1360-h1020-rw",
        location="Patershol",
        seats="20-30",
        coffee_price="£5",
    )

    if cafe is None:
        flash('Cafe not found.', 'error')
        return redirect(url_for('main.home'))

    return render_template(
        "listing.html",
        cafe=cafe,
        website_title=cafe.name
    )
