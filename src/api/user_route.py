from sqlite3 import IntegrityError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.sessions import get_session
from src.security import require_l1, require_l2
from src.models.user import User, UserCreate, UserRead



router = APIRouter(prefix="/users",
                   tags=["users"])

@router.post(
    "/",
    response_model=UserRead,
    status_code=201,
    description="Create a new user."
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