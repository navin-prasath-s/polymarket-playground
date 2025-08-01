from decimal import Decimal
from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.sessions import get_session
from src.security import require_l1, require_l2
from src.models.user import User, UserCreate, UserRead, UserUpdate

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
            name=user.name,
            balance=user.balance
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
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
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
        user_db = db.exec(select(User).where(User.name == user_input.name)).scalar_one_or_none()
        if not user_db:
            raise HTTPException(404, f"User {user_input.name} not found")
        if user_input.balance is None:
            user_db.balance = Decimal("10000.00")
        else:
            user_db.balance = user_input.balance

        db.add(user_db)
        db.commit()
        db.refresh(user_db)
        return user_db

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


