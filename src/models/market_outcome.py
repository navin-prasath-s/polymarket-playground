from typing import TYPE_CHECKING, Optional

from sqlmodel import SQLModel, Field, Relationship


if TYPE_CHECKING:
    from src.models.market import Market

class MarketOutcomeBase(SQLModel):
    class Config:
        from_attributes = True


class MarketOutcome(MarketOutcomeBase, table=True):
    __tablename__ = "market_outcomes"

    market: str = Field(foreign_key="markets.condition_id",
                        primary_key=True)

    token: str = Field(primary_key=True)

    outcome_text: str = Field(default=None)

    is_winner: bool = Field(default=False)

    market_obj: Optional["Market"] = Relationship(back_populates="outcomes")