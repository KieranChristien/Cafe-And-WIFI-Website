from datetime import datetime, date, time
from decimal import Decimal
from sqlalchemy import (Boolean, CheckConstraint, ForeignKey, Integer, Numeric, Select, String, Time, UniqueConstraint,
                        func, select, and_, or_, false, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Literal, Optional

from web.extensions import db
from web.services.clock import get_current_time, get_local_time

AttributeCategory = Literal["amenity", "feature", "payment"]

# Association table connecting cafés and attributes
cafe_attributes = db.Table(
    "cafe_attributes",
    db.Column(
        "cafe_id",
        ForeignKey("cafe.id"),
        primary_key=True
    ),
    db.Column(
        "attribute_id",
        ForeignKey("cafe_attribute.id"),
        primary_key=True
    )
)


# Cafe TABLE Configuration
class Cafe(db.Model):
    __tablename__ = "cafe"

    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_cafe_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_cafe_longitude",
        ),
        CheckConstraint(
            """
            (latitude IS NULL AND longitude IS NULL)
            OR
            (latitude IS NOT NULL AND longitude IS NOT NULL)
            """,
            name="ck_cafe_coordinates_both_or_none",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(250),
        nullable=False
    )

    overview: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    phone_number: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    img_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    img_public_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    img_asset_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Address
    location: Mapped[str] = mapped_column(
        String(250),
        nullable=False
    )

    address_line_1: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )

    address_line_2: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Geographic coordinates
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )

    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )

    # Geocoding source information
    location_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    location_provider_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    seats: Mapped[str] = mapped_column(
        String(250),
        nullable=False
    )

    coffee_price: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True
    )

    timezone: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    is_manually_closed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    manual_closed_message: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )

    # Many-to-many relationship with CafeAttribute
    attributes: Mapped[list["CafeAttribute"]] = relationship(
        secondary=cafe_attributes,
        back_populates="cafes",
        order_by="CafeAttribute.id",
    )

    # One-to-many relationship with CafeReview
    opening_hours: Mapped[list["CafeOpeningHour"]] = relationship(
        back_populates="cafe",
        cascade="all, delete-orphan",
        order_by="CafeOpeningHour.weekday",
    )

    # One-to-many relationship with CafePhotos
    photos: Mapped[list["CafePhoto"]] = relationship(
        back_populates="cafe",
        cascade="all, delete-orphan",
        order_by="CafePhoto.id",
    )

    # One-to-many relationship with CafeReview
    reviews: Mapped[list["CafeReview"]] = relationship(
        back_populates="cafe",
        cascade="all, delete-orphan",
        order_by="CafeReview.id",
    )

    @property
    def amenities(self):
        return [
            attribute
            for attribute in self.attributes
            if attribute.category == "amenity"
        ]

    @property
    def features(self):
        return [
            attribute
            for attribute in self.attributes
            if attribute.category == "feature"
        ]

    @property
    def payments(self):
        return [
            attribute
            for attribute in self.attributes
            if attribute.category == "payment"
        ]

    @property
    def average_rating(self) -> float | None:
        return db.session.scalar(
            select(func.avg(CafeReview.rating))
            .where(CafeReview.cafe_id == self.id)
        )

    @property
    def operating_status(self) -> str:
        from web.services.opening_hours import get_operating_status

        return get_operating_status(self)

    @property
    def next_opening_time(self) -> datetime | None:
        from web.services.opening_hours import get_next_opening_time
        return get_next_opening_time(self)

    @property
    def next_closing_time(self) -> datetime | None:
        from web.services.opening_hours import get_next_closing_time
        return get_next_closing_time(self)

    # Attribute management

    def add_attribute(self, attribute: "CafeAttribute") -> bool:
        if attribute in self.attributes:
            return False

        self.attributes.append(attribute)
        return True

    def remove_attribute(self, attribute: "CafeAttribute") -> bool:
        if attribute not in self.attributes:
            return False

        self.attributes.remove(attribute)
        return True

    # Review management

    def add_review(self, review: "CafeReview") -> bool:
        assigned_cafe: Optional["Cafe"] = getattr(review, "cafe", None)
        assigned_cafe_id: Optional[int] = getattr(review, "cafe_id", None)

        if assigned_cafe is self:
            return False

        if assigned_cafe is not None:
            raise ValueError("Review already belongs to another cafe")

        if assigned_cafe_id is not None:
            if self.id is not None and assigned_cafe_id == self.id:
                return False

            raise ValueError("Review already belongs to another cafe")

        self.reviews.append(review)
        return True

    def remove_review(self, review: "CafeReview") -> bool:
        if review not in self.reviews:
            return False

        self.reviews.remove(review)
        return True

    def to_dict(self):
        data = {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

        data["payments"] = self.payments
        data["features"] = self.features
        data["amenities"] = self.amenities
        data["average_rating"] = self.average_rating
        data["operating_status"] = self.operating_status
        data["next_opening_time"] = self.next_opening_time
        data["next_closing_time"] = self.next_closing_time

        data["attributes"] = [cafe_attribute.to_dict() for cafe_attribute in self.attributes]
        data["opening_hours"] = [opening_hour.to_dict() for opening_hour in self.opening_hours]
        data["reviews"] = [cafe_review.to_dict() for cafe_review in self.reviews]

        return data


class CafeAttribute(db.Model):
    __tablename__ = "cafe_attribute"

    __table_args__ = (
        CheckConstraint(
            "category IN ('feature', 'amenity', 'payment')",
            name="ck_cafe_attribute_category"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category: Mapped[AttributeCategory] = mapped_column(String(50), nullable=False)

    cafes: Mapped[list["Cafe"]] = relationship(
        secondary=cafe_attributes,
        back_populates="attributes"
    )

    @classmethod
    def get_by_category(cls, category: AttributeCategory) -> list["CafeAttribute"]:
        return db.session.scalars(
            select(cls).where(cls.category == category)
        ).all()

    def to_dict(self):
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class CafeOpeningHour(db.Model):
    __tablename__ = "cafe_opening_hour"

    __table_args__ = (
        CheckConstraint(
            "weekday BETWEEN 0 AND 6",
            name="ck_cafe_opening_hour_weekday"
        ),
        CheckConstraint(
            """
            (opens_at IS NULL AND closes_at IS NULL)
            OR
            (opens_at IS NOT NULL AND closes_at IS NOT NULL)
            """,
            name="ck_cafe_opening_hour_both_times_set",
        ),
        CheckConstraint(
            "opens_at IS NULL OR opens_at <> closes_at",
            name="ck_cafe_opening_hour_different_times",
        ),
        UniqueConstraint(
            "cafe_id",
            "weekday",
            name="uq_cafe_opening_hour_cafe_weekday",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    cafe_id: Mapped[int] = mapped_column(
        ForeignKey("cafe.id"),
        nullable=False,
        index=True,
    )

    # Monday = 0, Sunday = 6
    weekday: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    opens_at: Mapped[Time | None] = mapped_column(
        Time,
        nullable=True,
    )

    closes_at: Mapped[Time | None] = mapped_column(
        Time,
        nullable=True,
    )

    cafe: Mapped["Cafe"] = relationship(
        back_populates="opening_hours",
    )

    @property
    def is_closed(self) -> bool:
        return self.opens_at is None and self.closes_at is None

    @property
    def is_overnight(self) -> bool:
        if self.is_closed:
            return False

        return bool(self.closes_at < self.opens_at)

    def to_dict(self):
        return {
            "id": self.id,
            "cafe_id": self.cafe_id,
            "weekday": self.weekday,
            "opens_at": (
                self.opens_at.isoformat()
                if self.opens_at else None
            ),
            "closes_at": (
                self.closes_at.isoformat()
                if self.closes_at else None
            ),
            "is_closed": self.is_closed,
            "is_overnight": self.is_overnight,
        }


class CafePhoto(db.Model):
    __tablename__ = "cafe_photo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    cafe_id: Mapped[int] = mapped_column(
        ForeignKey("cafe.id"),
        nullable=False,
        index=True,
    )

    img_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    img_public_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    img_asset_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    cafe: Mapped["Cafe"] = relationship(
        back_populates="photos",
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class CafeReview(db.Model):
    __tablename__ = "cafe_review"

    __table_args__ = (
        CheckConstraint(
            "rating BETWEEN 1 AND 5",
            name="ck_cafe_review_rating"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cafe_id: Mapped[int] = mapped_column(
        ForeignKey("cafe.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    body: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    cafe: Mapped["Cafe"] = relationship(
        back_populates="reviews"
    )

    def to_dict(self):
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


def add_attribute(cafe_id: int, attribute_slug: str) -> bool:
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        raise LookupError("Cafe not found")

    attribute = db.session.scalar(
        select(CafeAttribute).where(
            CafeAttribute.slug == attribute_slug
        )
    )

    if attribute is None:
        raise LookupError("Attribute not found")

    return cafe.add_attribute(attribute)


def remove_attribute(cafe_id: int, attribute_slug: str) -> bool:
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        raise LookupError("Cafe not found")

    attribute = db.session.scalar(
        select(CafeAttribute).where(
            CafeAttribute.slug == attribute_slug
        )
    )

    if attribute is None:
        raise LookupError("Attribute not found")

    return cafe.remove_attribute(attribute)


def filter_by_attribute(
        stmt: Select[tuple[Cafe]],
        attributes: list[str],
        category: AttributeCategory | None = None
) -> Select[tuple[Cafe]]:
    for slug in attributes:
        if not slug:
            continue

        criterion = CafeAttribute.slug == slug
        if category is not None:
            criterion = db.and_(
                CafeAttribute.category == category,
                criterion,
            )

        stmt = stmt.where(
            Cafe.attributes.any(criterion)
        )

    return stmt


def filter_open_now(
        stmt: Select[tuple[Cafe]],
) -> Select[tuple[Cafe]]:
    current_time = get_current_time()

    # Retrieve only the distinct timezones belonging to
    # cafés that have passed the other filters.
    timezone_stmt = (
        stmt.with_only_columns(
            Cafe.timezone,
            maintain_column_froms=True,
        )
        .order_by(None)
        .distinct()
    )

    timezones = db.session.scalars(timezone_stmt).all()

    timezone_conditions = []

    for timezone_name in timezones:
        local_now = get_local_time(current_time, timezone_name)

        if local_now is None:
            continue

        local_clock = local_now.time().replace(tzinfo=None)

        weekday = local_now.weekday()
        yesterday = (weekday - 1) % 7

        # Check today's opening hours.
        today_open = Cafe.opening_hours.any(
            and_(
                CafeOpeningHour.weekday == weekday,

                or_(
                    # Normal opening hours.
                    and_(
                        CafeOpeningHour.opens_at
                        < CafeOpeningHour.closes_at,

                        CafeOpeningHour.opens_at <= local_clock,
                        CafeOpeningHour.closes_at > local_clock,
                    ),

                    # Overnight opening hours.
                    and_(
                        CafeOpeningHour.opens_at
                        > CafeOpeningHour.closes_at,

                        CafeOpeningHour.opens_at <= local_clock,
                    ),
                ),
            )
        )

        # Check whether yesterday's overnight schedule
        # extends into today.
        yesterday_open = Cafe.opening_hours.any(
            and_(
                CafeOpeningHour.weekday == yesterday,

                CafeOpeningHour.opens_at
                > CafeOpeningHour.closes_at,

                CafeOpeningHour.closes_at > local_clock,
            )
        )

        # Group the SQL conditions by timezone.
        timezone_conditions.append(
            and_(
                Cafe.timezone == timezone_name,

                Cafe.is_manually_closed.is_(False),

                or_(
                    today_open,
                    yesterday_open,
                ),
            )
        )

    if not timezone_conditions:
        return stmt.where(Cafe.id.in_([]))

    return stmt.where(
        or_(*timezone_conditions)
    )


def filter_open_on_date(
        stmt: Select[tuple[Cafe]],
        day: date,
) -> Select[tuple[Cafe]]:
    weekday = day.weekday()
    previous_weekday = (weekday - 1) % 7

    # Check whether the cafe has opening hours today.
    opens_today = Cafe.opening_hours.any(
        and_(
            CafeOpeningHour.weekday == weekday,
            CafeOpeningHour.opens_at.is_not(None),
        )
    )

    # Check whether yesterday's overnight hours
    # extend into today.
    overnight_from_yesterday = Cafe.opening_hours.any(
        and_(
            CafeOpeningHour.weekday == previous_weekday,
            CafeOpeningHour.opens_at > CafeOpeningHour.closes_at,
            CafeOpeningHour.closes_at > time.min,
        )
    )

    return stmt.where(
        Cafe.is_manually_closed.is_(False),
        or_(
            opens_today,
            overnight_from_yesterday,
        )
    )


def get_attributes_from_slugs(category: AttributeCategory, attribute_slugs: list[str]) -> list[CafeAttribute]:
    if not attribute_slugs:
        return []

    attributes = db.session.scalars(
        select(CafeAttribute).where(
            CafeAttribute.category == category,
            CafeAttribute.slug.in_(attribute_slugs),
        )
    ).all()

    # Preserve the order in which the user selected them.
    attributes_by_slug = {
        attribute.slug: attribute
        for attribute in attributes
    }

    return [
        attributes_by_slug[slug]
        for slug in dict.fromkeys(attribute_slugs)
        if slug in attributes_by_slug
    ]


def get_review_stats(cafe_ids: list[int]) -> dict[int, tuple[float | None, int]]:
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

    return review_stats


def get_review_stats_subquery():
    return (
        db.select(
            CafeReview.cafe_id.label("cafe_id"),
            db.func.avg(CafeReview.rating).label("average_rating"),
            db.func.count(CafeReview.id).label("review_count"),
        )
        .group_by(CafeReview.cafe_id)
        .subquery()
    )


def join_review_stats(stmt: Select[tuple[Cafe]]):
    review_stats = get_review_stats_subquery()

    stmt = stmt.outerjoin(
        review_stats,
        Cafe.id == review_stats.c.cafe_id,
    )

    average_rating = db.func.coalesce(
        review_stats.c.average_rating,
        0,
    )

    review_count = db.func.coalesce(
        review_stats.c.review_count,
        0,
    )

    return stmt, average_rating, review_count
