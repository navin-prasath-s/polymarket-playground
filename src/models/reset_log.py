from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import ConfigDict
from sqlalchemy import ForeignKeyConstraint
from sqlmodel import SQLModel, Field


class ResetLogBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class ResetLog(ResetLogBase, table=True):
    __tablename__ = "reset_logs"


    user_name: str = Field(foreign_key="users.name", primary_key=True)
    balance_reset: Annotated[Decimal, Field(ge=0,
                                            max_digits=14,
                                            decimal_places=2,
                                            nullable=False)]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))