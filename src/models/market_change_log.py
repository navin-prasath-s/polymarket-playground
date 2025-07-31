from datetime import datetime, timezone
from enum import Enum

from pydantic import ConfigDict
from sqlmodel import SQLModel, Field

class MarketChangeType(str, Enum):
    ADDED = "added"
    DELETED = "deleted"


class MarketChangeLogBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)

class MarketChangeLog(MarketChangeLogBase, table=True):
    __tablename__ = "market_change_logs"

    id: int | None = Field(primary_key=True)
    condition_id: str
    change_type: MarketChangeType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))