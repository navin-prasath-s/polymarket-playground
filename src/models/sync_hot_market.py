from pydantic import ConfigDict
from sqlmodel import SQLModel, Field


class SyncHotMarketBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class SyncHotMarket(SyncHotMarketBase, table=True):
    __tablename__ = "sync_hot_markets"

    condition_id: str = Field(primary_key=True)
    question: str
    description: str
    tokens: str


