from typing import Literal, Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, select, func, Select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from web.extensions import db

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    map_url: Mapped[str] = mapped_column(String(500), nullable=False)
    img_url: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str] = mapped_column(String(250), nullable=False)
    seats: Mapped[str] = mapped_column(String(250), nullable=False)
    coffee_price: Mapped[str | None] = mapped_column(String(250), nullable=True)

    # Many-to-many relationship with CafeAttribute
    attributes: Mapped[list["CafeAttribute"]] = relationship(
        secondary=cafe_attributes,
        back_populates="cafes",
        order_by="CafeAttribute.id",
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

        data["attributes"] = [cafe_attribute.to_dict() for cafe_attribute in self.attributes]
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
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "category": self.category
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
            "id": self.id,
            "name": self.name,
            "body": self.body,
            "rating": self.rating,
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

def join_review_stats(stmt):
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
