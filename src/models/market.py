from typing import TYPE_CHECKING

from pydantic import ConfigDict
from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from src.models.market_outcome import MarketOutcome


class MarketBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class Market(MarketBase, table=True):
    __tablename__ = "markets"

    condition_id: str = Field(primary_key=True)
    is_tradable: bool = Field(default=True)

    outcomes: list["MarketOutcome"] | None = Relationship(back_populates="market_obj")