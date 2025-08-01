import logging
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.sessions import get_session
from src.security import require_l1, require_l2
from src.models.user import User, UserCreate, UserRead, UserUpdate


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users",
                   tags=["users"])

@router.post(
    "/",
    response_model=UserRead,
    status_code=201,
    description="Create a new user.",
    responses={
        409: {"description": "User already exists"},
        500: {"description": "An unexpected error occurred."}
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
    "/reset-user",
    response_model=UserUpdate,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_l1)],
    description="Reset a user’s balance (omitting `balance` resets to 10000.00).",
    responses={
        404: {"description": "User not found"},
        500: {"description": "Unexpected server error"},
    },
)
async def reset_user_balance(
    user_input: UserUpdate,
    db: Session = Depends(get_session),
):
    try:
        user_db = db.exec(
            select(User).where(User.name == user_input.name)
        ).one_or_none()
        logger.debug(f"Resetting user {user_input.name} with balance {user_input.balance}")
        if not user_db:
            raise HTTPException(404, f"User {user_input.name} not found")

        if user_input.balance is None:
            user_db.balance = Decimal("10000.00")
        else:
            user_db.balance = user_input.balance
        logger.debug(f"User {user_input.name} balance set to {user_db.balance}")
        db.add(user_db)
        logger.debug(f"Committing changes for user {user_input.name}")
        db.commit()
        logger.debug(f"Refreshing user {user_input.name} after commit")
        db.refresh(user_db)
        logger.debug(f"User {user_input.name} reset successfully")
        return user_db

    except HTTPException:
        raise

    except Exception as e:
        logger.debug(f"Failed to reset user {user_input.name}: {e}"),
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


