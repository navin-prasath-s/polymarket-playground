from decimal import Decimal
from typing import Annotated

from pydantic import ConfigDict
from sqlalchemy import CheckConstraint, ForeignKeyConstraint
from sqlmodel import SQLModel, Field



class UserPositionBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)

class UserPosition(UserPositionBase, table=True):
    __tablename__ = "user_positions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["market", "token"],
            ["market_outcomes.market", "market_outcomes.token"]
        ),
        CheckConstraint('shares >= 0', name='_user_shares_non_negative')
    )

    user_name: str = Field(foreign_key="users.name", primary_key=True)
    market: str = Field(primary_key=True)
    token: str = Field(primary_key=True)
    shares: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')


class UserPositionRead(UserPositionBase):
    market: str
    token: str
    shares: Annotated[Decimal, Field(ge=0,
                                     max_digits=14,
                                     decimal_places=2,
                                     nullable=False)] = Decimal('0')