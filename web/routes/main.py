from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

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
        if not slug:
            continue

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
        if not slug:
            continue

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
        if not slug:
            continue

        stmt = stmt.where(
            Cafe.attributes.any(
                db.and_(
                    CafeAttribute.category == 'feature',
                    CafeAttribute.slug == slug
                )
            )
        )

    return stmt


def _get_selected_attributes(category, slugs):
    if not slugs:
        return []

    attributes = db.session.execute(
        db.select(CafeAttribute).where(
            CafeAttribute.category == category,
            CafeAttribute.slug.in_(slugs)
        )
    ).scalars().all()

    # Preserve the order in which the user selected them.
    attributes_by_slug = {
        attribute.slug: attribute
        for attribute in attributes
    }

    return [
        attributes_by_slug[slug]
        for slug in dict.fromkeys(slugs)
        if slug in attributes_by_slug
    ]


def _pagination_url(page):
    args = request.args.to_dict(flat=False)
    args['page'] = page
    return url_for('main.home', **args)


def _remove_filter_url(param, value=None):
    args = request.args.to_dict(flat=False)

    if value is None:
        # Remove the entire parameter, e.g. rating.
        args.pop(param, None)
    else:
        # Remove only the matching value, e.g. one amenity.
        remaining = [
            item for item in args.get(param, [])
            if item != value
        ]

        if remaining:
            args[param] = remaining
        else:
            args.pop(param, None)

    # Return to the first page after changing filters.
    args.pop('page', None)

    return url_for('main.home', **args)


@main.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    per_page = 4

    stmt = _get_filtered_cafes().order_by(Cafe.id.asc())

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

    selected_amenity_slugs = request.args.getlist('amenities')
    selected_payment_slugs = request.args.getlist('payments')
    selected_feature_slugs = request.args.getlist('features')

    # Resolve slugs into CafeAttribute instances.
    selected_amenities = _get_selected_attributes(
        'amenity', selected_amenity_slugs
    )

    selected_payments = _get_selected_attributes(
        'payment', selected_payment_slugs
    )

    selected_features = _get_selected_attributes(
        'feature', selected_feature_slugs
    )

    selected_prices = request.args.getlist('price')

    selected_rating = request.args.get('rating', -1, type=float)
    selected_open_date = request.args.get('open_date', '')

    return render_template(
        "index.html",
        cafes=pagination.items,
        pagination=pagination,
        pagination_url=_pagination_url,
        remove_filter_url=_remove_filter_url,
        cafe_amenities=cafe_amenities,
        cafe_features=cafe_features,
        cafe_payments=cafe_payments,
        feature_options=feature_options,
        selected_amenities=selected_amenities,
        selected_payments=selected_payments,
        selected_features=selected_features,
        selected_prices=selected_prices,
        selected_rating=selected_rating,
        selected_open_date=selected_open_date,
    )


@main.route('/cafes/count')
def cafe_count():
    stmt = _get_filtered_cafes()

    count = db.session.scalar(
        db.select(db.func.count()).select_from(stmt.subquery())
    )

    return jsonify({'count': count})
