from flask import Blueprint, jsonify, render_template, request, url_for

from web.extensions import db
from web.models import Cafe, CafeAttribute, get_review_stats, CafeReview

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

    # Retrieve and paginate cafés.
    stmt = _get_filtered_cafes().order_by(Cafe.id.asc())

    pagination = db.paginate(
        stmt,
        page=page,
        per_page=per_page,
        error_out=False
    )

    cafe_ids = [cafe.id for cafe in pagination.items]

    review_stats = {}

    if cafe_ids:
        results = db.session.execute(
            db.select(
                CafeReview.cafe_id,
                db.func.avg(CafeReview.rating).label("average_rating"),
                db.func.count(CafeReview.id).label("review_count"),
            )
            .where(CafeReview.cafe_id.in_(cafe_ids))
            .group_by(CafeReview.cafe_id)
        ).all()

        review_stats = {
            cafe_id: (average_rating, review_count)
            for cafe_id, average_rating, review_count in results
        }

    cafes = []

    for cafe in pagination.items:
        average_rating, review_count = review_stats.get(
            cafe.id,
            (None, 0)
        )

        cafes.append({
            "cafe": cafe,
            "average_rating": average_rating,
            "review_count": review_count,
        })

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

    filters_applied = request.args.get('filters_applied', False, type=bool)

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

    filters = {
        "applied": filters_applied,
        "amenities": selected_amenities,
        "payments": selected_payments,
        "features": selected_features,
        "price": selected_prices,
        "rating": selected_rating,
        "open_date": selected_open_date,
    }

    return render_template(
        "index.html",
        cafes=cafes,
        pagination=pagination,
        pagination_url=_pagination_url,
        remove_filter_url=_remove_filter_url,
        cafe_amenities=cafe_amenities,
        cafe_features=cafe_features,
        cafe_payments=cafe_payments,
        feature_options=feature_options,
        filters=filters
    )


@main.route('/cafes/count')
def cafe_count():
    stmt = _get_filtered_cafes()

    count = db.session.scalar(
        db.select(db.func.count()).select_from(stmt.subquery())
    )

    return jsonify({'count': count})
