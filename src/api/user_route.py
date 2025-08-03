import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlmodel import Session, select

from src.sessions import get_session
from src.security import require_l1, require_l2
from src.models.user import User, UserCreate, UserRead, BalanceUpdate
from src.models.user_position import UserPositionRead, UserPosition


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users",
                   tags=["users"])

@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    description="Create a new user.",
    responses={
        status.HTTP_409_CONFLICT: {"description": "User already exists"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "An unexpected error occurred."}
    }
)
async def create_user(
        user: UserCreate,
        db: Session = Depends(get_session),
):
    try:
        created_user = User(
            ** user.model_dump()
        )
        db.add(created_user)
        db.commit()
        db.refresh(created_user)
        return created_user

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists"
        )
    except Exception as e:
        logger.exception(f"Failed to create user {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred."
        )


# TODO: create a table to log the resets

@router.patch(
    "/{user_name}/reset-balance",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_l1)],
    description="Reset a user’s balance (omitting `balance` resets to 10000.00).",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def reset_user_balance(
    user_name: str,
    user_input: BalanceUpdate = Body(default=None),
    db: Session = Depends(get_session),
):
    try:
        user_db = db.exec(
            select(User).where(User.name == user_name)
        ).one_or_none()
        logger.debug(f"Resetting user {user_name} with balance {user_input.balance}")
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_name} not found"
            )

        if user_input.balance is None:
            user_db.balance = Decimal("10000.00")
        else:
            user_db.balance = user_input.balance
        logger.debug(f"User {user_name} balance set to {user_db.balance}")
        db.add(user_db)
        logger.debug(f"Committing changes for user {user_name}")
        db.commit()
        logger.debug(f"Refreshing user {user_name} after commit")
        db.refresh(user_db)
        logger.debug(f"User {user_name} reset successfully")
        return user_db

    except HTTPException:
        raise

    except Exception as e:
        logger.debug(f"Failed to reset user {user_name}: {e}"),
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


@router.get(
    "/{user_name}/positions",
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

    # Fetch all positions
    positions = db.exec(
        select(UserPosition).where(UserPosition.user_name == user_name)
    ).all()

    return positions



