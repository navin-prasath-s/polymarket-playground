from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, TYPE_CHECKING

from pydantic import ConfigDict
from sqlalchemy import ForeignKeyConstraint, CheckConstraint
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from src.models.order_fill import OrderFill


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class OrderStatus(str, Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class OrderBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)

class Order(OrderBase, table=True):
    __tablename__ = "orders"

    __table_args__ = (
        ForeignKeyConstraint(
            ["market", "token"],
            ["market_outcomes.market", "market_outcomes.token"]
        ),
        CheckConstraint(
            "shares >= 0",
            name="_order_shares_non_negative"
        ),
        CheckConstraint(
            "amount_usdc >= 0",
            name="_amount_usdc_non_negative"
        ),
    )

    order_id: int | None = Field(primary_key=True)
    user_name: int = Field(foreign_key="users.name",nullable=False)
    market: str = Field(nullable=False)
    token: str = Field(nullable=False)
    side: OrderSide = Field(nullable=False)
    order_type: OrderType = Field(nullable=False)
    status: OrderStatus = Field(nullable=False)
    amount_usdc: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')
    shares: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fills: list["OrderFill"] | None = Relationship(back_populates="order_obj")


class OrderBuyCreate(OrderBase):
    market: str
    token: str
    order_type: OrderType
    amount_usdc: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')

class OrderSellCreate(OrderBase):
    market: str
    token: str
    order_type: OrderType
    shares: Annotated[Decimal, Field(ge=0,
                                max_digits=14,
                                decimal_places=2,
                                nullable=False)] = Decimal('0')