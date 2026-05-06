"""
Create price_alerts table for user-defined price alerts.

Guarda alertas del tipo "avisame cuando Bitcoin supere los $100k".
El pipeline las checkea después de cada snapshot y las marca
como triggered cuando se cumplen.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("coin_id", sa.String(100), nullable=False, index=True),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("condition", sa.String(10), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Integer(), default=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("price_alerts")
