from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


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


class UserRead(BaseModel):
    name: str
    balance: Decimal


class OrderRead(BaseModel):
    user_name: str
    market: str
    token: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    amount_usdc: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    shares: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    created_at: datetime
    updated_at: datetime


class UserPositionRead(BaseModel):
    market: str
    token: str
    shares: Decimal = Field(ge=0, max_digits=14, decimal_places=2)