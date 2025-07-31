from typing import TYPE_CHECKING

from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from src.models.market_outcome import MarketOutcome


class MarketBase(SQLModel):
    class Config:
        from_attributes = True


class Market(MarketBase, table=True):
    __tablename__ = "markets"

    condition_id: str = Field(primary_key=True)
    market_slug: str
    is_tradable: bool = Field(default=True)

    outcomes: list["MarketOutcome"] | None = Relationship(back_populates="market_obj")