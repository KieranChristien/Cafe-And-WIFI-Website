from flask import Blueprint, current_app, flash, redirect, render_template, url_for

from web.extensions import db
from web.models import Cafe, CafeAttribute

main = Blueprint('main', __name__)


def _get_filtered_cafes():
    stmt = db.select(Cafe)

    amenities = request.args.getlist('amenities')
    payments = request.args.getlist('payments')
    features = request.args.getlist('features')

    # Every selected amenity must match
    for slug in amenities:
        stmt = stmt.where(
            Cafe.attributes.any(
                db.and_(
                    CafeAttribute.category == 'amenity',
                    CafeAttribute.slug == slug
                )
            )
        )

    # Every selected payment method must match
    for slug in payments:
        stmt = stmt.where(
            Cafe.attributes.any(
                db.and_(
                    CafeAttribute.category == 'payment',
                    CafeAttribute.slug == slug
                )
            )
        )

    # Every selected feature must match
    for slug in features:
        stmt = stmt.where(
            Cafe.attributes.any(
                db.and_(
                    CafeAttribute.category == 'feature',
                    CafeAttribute.slug == slug
                )
            )
        )

    return stmt

def _pagination_url(page):
    args = request.args.to_dict(flat=False)
    args['page'] = page
    return url_for('main.home', **args)

@main.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    per_page = 6

    stmt = db.select(Cafe).order_by(Cafe.id.asc())

    pagination = db.paginate(
        stmt,
        page=page,
        per_page=per_page,
        error_out=False
    )

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
        cafes=pagination.items,
        pagination=pagination,
        pagination_url=_pagination_url,
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
