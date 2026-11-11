from flask import Blueprint, jsonify, render_template, request, url_for
from typing import Literal, cast

from web.extensions import db
from web.models import (Cafe, CafeAttribute, filter_by_attribute, get_attributes_from_slugs,
                        get_review_stats, join_review_stats)

main = Blueprint('main', __name__)

SortTypes = Literal[
    "top-rated",
    "most-reviewed",
    "recently-added"
]

SORT_LABELS = {
    "top-rated": "Top rated",
    "most-reviewed": "Most reviewed",
    "recently-added": "Recently added",
}


def _apply_sort(stmt, sort_by: SortTypes):
    stmt = stmt.order_by(None)

    if sort_by == "recently-added":
        return stmt.order_by(Cafe.id.desc())

    stmt, average_rating, review_count = join_review_stats(stmt)

    if sort_by == "top-rated":
        return stmt.order_by(
            average_rating.desc(),
            review_count.desc(),
            Cafe.id.asc(),
        )
    elif sort_by == "most-reviewed":
        return stmt.order_by(
            review_count.desc(),
            average_rating.desc(),
            Cafe.id.asc(),
        )
    else:
        return stmt.order_by(Cafe.id.asc())


def _get_filtered_cafes():
    stmt = db.select(Cafe)

    amenities = request.args.getlist('amenities')
    payments = request.args.getlist('payments')
    features = request.args.getlist('features')

    # Every selected amenity must match
    stmt = filter_by_attribute(stmt, amenities, 'amenity')
    stmt = filter_by_attribute(stmt, payments, 'payment')
    stmt = filter_by_attribute(stmt, features, 'feature')

    rating = request.args.get('rating', -1, type=float)

    if rating >= 0:
        stmt, average_rating, _ = join_review_stats(stmt)
        stmt = stmt.where(average_rating >= rating)

    return stmt


def _get_sort_by() -> SortTypes:
    value = request.args.get("sort_by", "top-rated")

    if value not in SORT_LABELS:
        return "top-rated"

    return cast(SortTypes, value)


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


def _sort_by_url(sort_by: SortTypes | None = None):
    args = request.args.to_dict(flat=False)

    args['sort_by'] = [sort_by or 'top-rated']

    # Return to the first page after changing filters.
    args.pop('page', None)

    return url_for('main.home', **args)


@main.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    per_page = 4

    sort_by = _get_sort_by()

    # Retrieve and paginate cafés.
    stmt = _get_filtered_cafes()
    stmt = _apply_sort(stmt, sort_by)

    pagination = db.paginate(
        stmt,
        page=page,
        per_page=per_page,
        error_out=False
    )

    review_stats = get_review_stats(
        [cafe.id for cafe in pagination.items]
    )

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

    cafe_amenities = CafeAttribute.get_by_category("amenity")
    cafe_payments = CafeAttribute.get_by_category("payment")
    cafe_features = CafeAttribute.get_by_category("feature")

    feature_options = [
        {
            "name": feature.name,
            "slug": feature.slug,
        }
        for feature in cafe_features
    ]

    filters_applied = request.args.get('filters_applied', False, type=bool)
    selected_amenity_slugs = request.args.getlist('amenities')
    selected_payment_slugs = request.args.getlist('payments')
    selected_feature_slugs = request.args.getlist('features')

    # Resolve slugs into CafeAttribute instances.
    selected_amenities = get_attributes_from_slugs(
        'amenity', selected_amenity_slugs
    )

    selected_payments = get_attributes_from_slugs(
        'payment', selected_payment_slugs
    )

    selected_features = get_attributes_from_slugs(
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
        "prices": selected_prices,
        "rating": selected_rating,
        "open_date": selected_open_date,
    }

    return render_template(
        "index.html",
        cafes=cafes,
        pagination=pagination,
        pagination_url=_pagination_url,
        remove_filter_url=_remove_filter_url,
        sort_by_url=_sort_by_url,
        sort_by=sort_by,
        sort_label=SORT_LABELS[sort_by],
        cafe_amenities=cafe_amenities,
        cafe_features=cafe_features,
        cafe_payments=cafe_payments,
        feature_options=feature_options,
        filters=filters,
    )


@main.route('/cafes/count')
def cafe_count():
    stmt = _get_filtered_cafes()

    count = db.session.scalar(
        db.select(db.func.count()).select_from(stmt.subquery())
    )

    return jsonify({'count': count})
