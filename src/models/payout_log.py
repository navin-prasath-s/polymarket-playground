from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import ConfigDict
from sqlalchemy import ForeignKeyConstraint
from sqlmodel import SQLModel, Field


class PayoutLogBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class PayoutLog(PayoutLogBase, table=True):
    __tablename__ = "payout_logs"

    __table_args__ = (
        ForeignKeyConstraint(
            ["market", "token"],
            ["market_outcomes.market", "market_outcomes.token"]
        ),
    )

    user_id: int = Field(foreign_key="users.name", primary_key=True)
    market: str = Field(primary_key=True)
    token: str = Field(primary_key=True)
    shares_paid: Annotated[Decimal, Field(ge=0,
                                      max_digits=14,
                                      decimal_places=2,
                                      nullable=False)]
    is_winner: bool = Field(nullable=True, default=False)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
