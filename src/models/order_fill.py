from decimal import Decimal
from datetime import datetime, timezone
from typing import Annotated, TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from src.models.order import Order


class OrderFillBase(SQLModel):
    class Config:
        from_attributes = True


class OrderFill(OrderFillBase, table=True):
    __tablename__ = "order_fills"

    __table_args__ = (
        CheckConstraint(
            "fill_shares >= 0",
            name="_fill_shares_non_negative"
        ),
        CheckConstraint(
            "fill_price >= 0",
            name="_fill_price_non_negative"
        ),
    )

    fill_id: int | None = Field(primary_key=True)

    order_id: int = Field(
        foreign_key="orders.order_id",
        nullable=False,
    )

    fill_price: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')

    fill_shares: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')

    filled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    order_obj: Optional["Order"] = Relationship(back_populates="fills")