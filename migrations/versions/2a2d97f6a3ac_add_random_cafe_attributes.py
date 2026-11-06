"""Add random cafe attributes

Revision ID: 2a2d97f6a3ac
Revises: b506c78a2aaa
Create Date: 2026-11-04 00:21:31.767756

"""
from alembic import op
import sqlalchemy as sa
import random

# revision identifiers, used by Alembic.
revision = '2a2d97f6a3ac'
down_revision = 'b506c78a2aaa'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Define lightweight table references.
    cafe = sa.table(
        "cafe",
        sa.column("id", sa.Integer)
    )

    cafe_attribute = sa.table(
        "cafe_attribute",
        sa.column("id", sa.Integer),
        sa.column("category", sa.String)
    )

    cafe_attributes = sa.table(
        "cafe_attributes",
        sa.column("cafe_id", sa.Integer),
        sa.column("attribute_id", sa.Integer)
    )

    op.create_table(
        "_seeded_cafe_attributes_2a2d97f6a3ac",
        sa.Column("cafe_id", sa.Integer(), nullable=False),
        sa.Column("attribute_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("cafe_id", "attribute_id")
    )

    # Use a fixed seed so that the random choices are reproducible.
    rng = random.Random(20261104)

    # Get all existing cafes.
    cafe_ids = bind.execute(
        sa.select(cafe.c.id).order_by(cafe.c.id)
    ).scalars().all()

    # Get all available features and payment methods.
    attributes = bind.execute(
        sa.select(
            cafe_attribute.c.id,
            cafe_attribute.c.category
        )
        .where(
            cafe_attribute.c.category.in_(["feature", "payment"])
        )
        .order_by(cafe_attribute.c.id)
    ).mappings().all()

    features = [
        attribute["id"]
        for attribute in attributes
        if attribute["category"] == "feature"
    ]

    payments = [
        attribute["id"]
        for attribute in attributes
        if attribute["category"] == "payment"
    ]

    # Find existing associations to avoid duplicates.
    existing = bind.execute(
        sa.select(
            cafe_attributes.c.cafe_id,
            cafe_attributes.c.attribute_id
        )
    ).all()

    existing_by_cafe = {}

    for cafe_id, attribute_id in existing:
        existing_by_cafe.setdefault(cafe_id, set()).add(attribute_id)

    new_associations = []

    for cafe_id in cafe_ids:
        assigned = existing_by_cafe.get(cafe_id, set())

        # Only consider attributes that aren't already assigned.
        available_features = [
            attribute_id
            for attribute_id in features
            if attribute_id not in assigned
        ]

        available_payments = [
            attribute_id
            for attribute_id in payments
            if attribute_id not in assigned
        ]

        # Randomly select 1–3 features.
        if available_features:
            count = rng.randint(1, min(3, len(available_features)))
            selected_features = rng.sample(available_features, count)

        else:
            selected_features = []

        # Randomly select 1–2 payment methods.
        if available_payments:
            count = rng.randint(1, min(2, len(available_payments)))
            selected_payments = rng.sample(available_payments, count)

        else:
            selected_payments = []

        # Prepare association records.
        for attribute_id in selected_features + selected_payments:
            new_associations.append({
                "cafe_id": cafe_id,
                "attribute_id": attribute_id
            })

    # Insert all associations in one operation.
    if new_associations:
        bind.execute(
            cafe_attributes.insert(),
            new_associations
        )

        bind.execute(
            sa.table(
                "_seeded_cafe_attributes_2a2d97f6a3ac",
                sa.column("cafe_id", sa.Integer),
                sa.column("attribute_id", sa.Integer)
            ).insert(),
            new_associations
        )


def downgrade():
    bind = op.get_bind()

    cafe_attributes = sa.table(
        "cafe_attributes",
        sa.column("cafe_id", sa.Integer),
        sa.column("attribute_id", sa.Integer)
    )

    migration_log = sa.table(
        "_seeded_cafe_attributes_2a2d97f6a3ac",
        sa.column("cafe_id", sa.Integer),
        sa.column("attribute_id", sa.Integer)
    )

    # Delete only associations created by this migration.
    bind.execute(
        sa.delete(cafe_attributes).where(
            sa.exists(
                sa.select(1)
                .select_from(migration_log)
                .where(
                    migration_log.c.cafe_id == cafe_attributes.c.cafe_id,
                    migration_log.c.attribute_id == cafe_attributes.c.attribute_id
                )
            )
        )
    )

    # Remove the migration tracking table.
    op.drop_table("_seeded_cafe_attributes_2a2d97f6a3ac")
