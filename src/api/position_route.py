import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.models.user import User
from src.models.user_position import UserPositionRead, UserPosition
from src.sessions import get_session


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/positions",
                   tags=["positions"])


@router.get(
    "/{user_name}",
    response_model=list[UserPositionRead],
    status_code=status.HTTP_200_OK,
    description="Get all market positions for a given user.",
    responses={
        404: {"description": "User not found"},
    },
)
async def get_user_positions(
    user_name: str,
    db: Session = Depends(get_session),
):
    user = db.exec(select(User).where(User.name == user_name)).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_name}' not found"
        )

    positions = db.exec(
        select(UserPosition).where(UserPosition.user_name == user_name)
    ).all()

    return positions


@router.get(
    "",
    response_model=list[UserPositionRead],
    status_code=status.HTTP_200_OK,
    description="Get all user positions in the system.",
)
async def get_all_positions(
    db: Session = Depends(get_session),
):
    positions = db.exec(select(UserPosition)).all()
    return positions