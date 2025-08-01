from typing import Annotated
from decimal import Decimal

from pydantic import ConfigDict
from sqlmodel import SQLModel, Field
from sqlalchemy import CheckConstraint


class UserBase(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class User(UserBase, table=True):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_non_negative"),
    )

    name: str = Field(primary_key=True)
    balance: Annotated[Decimal, Field(ge=0,
                                      max_digits=14,
                                      decimal_places=2,
                                      nullable=True)] = Decimal("10000.00")

class UserCreate(UserBase):
    name: str
    balance: Annotated[Decimal, Field(ge=0,
                                      max_digits=14,
                                      decimal_places=2,
                                      nullable=True)] = Decimal("10000.00")

class UserRead(UserBase):
    name: str
    balance: Decimal

class UserUpdate(UserBase):
    name: str | None = None
    balance: Annotated[Decimal | None, Field(ge=0,
                                             max_digits=14,
                                             decimal_places=2,
                                             nullable=True)] = Decimal("10000.00")
