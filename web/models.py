from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from web.extensions import db

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
        order_by="CafeAttribute.id"
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

    def to_dict(self):
        data = {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

        data["attributes"] = [cafe_attribute.to_dict() for cafe_attribute in self.attributes]

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
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    cafes: Mapped[list["Cafe"]] = relationship(
        secondary=cafe_attributes,
        back_populates="attributes"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "category": self.category
        }


def add_attribute(cafe_id: int, attribute_slug: str) -> bool:
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        raise LookupError("Cafe not found")

    cafe_attribute = db.session.scalar(
        select(CafeAttribute).where(CafeAttribute.slug == attribute_slug)
    )

    if cafe_attribute is None:
        raise LookupError("Attribute not found")

    if cafe_attribute not in cafe.attributes:
        cafe.attributes.append(cafe_attribute)
        return True

    return False


def remove_attribute(cafe_id: int, attribute_slug: str) -> bool:
    cafe = db.session.get(Cafe, cafe_id)

    if cafe is None:
        raise LookupError("Cafe not found")

    cafe_attribute = db.session.scalar(
        select(CafeAttribute).where(CafeAttribute.slug == attribute_slug)
    )

    if cafe_attribute is None:
        raise LookupError("Attribute not found")

    if cafe_attribute in cafe.attributes:
        cafe.attributes.remove(cafe_attribute)
        return True

    return False
