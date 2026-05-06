"""
Create price_history table for cached historical data.

Guarda histórico de precios (7d, 30d, 90d) para que la API
sirva /api/history sin llamar a CoinGecko.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("coin_id", sa.String(100), primary_key=True),
        sa.Column("days", sa.Integer(), primary_key=True),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("price_history")
