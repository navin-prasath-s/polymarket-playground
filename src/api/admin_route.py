from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, delete

from src.models.order import Order
from src.models.user import User
from src.models.user_position import UserPosition
from src.sessions import get_session
from src.security import require_l2

router = APIRouter(prefix="/admin", tags=["admin"])


@router.delete(
    "/clear-all",
    status_code=status.HTTP_200_OK,
    description="Delete all users, orders, positions, and related data.",
    dependencies=[Depends(require_l2)],
)
async def clear_all_data(db: Session = Depends(get_session)):
    try:
        db.exec(delete(Order))
        db.exec(delete(UserPosition))
        db.exec(delete(User))
        db.commit()
        return {"success": True, "message": "All data cleared."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database clear failed: {e}"
        )