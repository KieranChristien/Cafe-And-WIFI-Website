"""Fix manually closed Boolean default

Revision ID: ed57f34fa479
Revises: bbe24b594f6f
Create Date: 2026-11-20 21:42:43.500962

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed57f34fa479'
down_revision = 'bbe24b594f6f'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cafe") as batch_op:
        batch_op.alter_column(
            "is_manually_closed",
            existing_type=sa.Boolean(),
            existing_server_default=sa.text("'false'"),
            server_default=sa.false(),
        )



def downgrade():
    with op.batch_alter_table("cafe") as batch_op:
        batch_op.alter_column(
            "is_manually_closed",
            existing_type=sa.Boolean(),
            existing_server_default=sa.false(),
            server_default=sa.text("'false'"),
        )
