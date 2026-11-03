from flask import Blueprint, current_app, flash, redirect, render_template, url_for

from web.extensions import db
from web.models import Cafe, CafeAttribute

main = Blueprint('main', __name__)


@main.route('/', methods=['GET', 'POST'])
def home():
    cafes = db.session.execute(db.select(Cafe)).scalars().all()
    cafe_amenities = db.session.execute(
        db.select(CafeAttribute).where(CafeAttribute.category == "amenity")
    ).scalars().all()

    cafe_features = db.session.execute(
        db.select(CafeAttribute).where(CafeAttribute.category == "feature")
    ).scalars().all()

    cafe_payments = db.session.execute(
        db.select(CafeAttribute).where(CafeAttribute.category == "payment")
    ).scalars().all()

    feature_options = [
        {
            "name": feature.name,
            "slug": feature.slug
        }
        for feature in cafe_features
    ]

    return render_template(
        "index.html",
        cafes=cafes,
        cafe_amenities=cafe_amenities,
        cafe_features=cafe_features,
        cafe_payments=cafe_payments,
        feature_options=feature_options,
    )


@main.route('/listing/<int:cafe_id>', methods=['GET', 'POST'])
def listing(cafe_id: int):
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        flash('Cafe not found.', 'error')
        return redirect(url_for('main.home'))

    return render_template("listing.html", cafe=cafe)
