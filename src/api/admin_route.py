from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, status, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlmodel import Session, delete

from src.models.market import Market
from src.models.market_change_log import MarketChangeLog
from src.models.market_outcome import MarketOutcome
from src.models.order import Order
from src.models.order_fill import OrderFill
from src.models.payout_log import PayoutLog
from src.models.sync_hot_market import SyncHotMarket
from src.models.user import User
from src.models.user_position import UserPosition
from src.models.reset_log import ResetLog
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
        db.exec(delete(MarketOutcome))
        db.exec(delete(MarketChangeLog))
        db.exec(delete(PayoutLog))
        db.exec(delete(ResetLog))
        db.exec(delete(SyncHotMarket))
        db.exec(delete(UserPosition))
        db.exec(delete(OrderFill))
        db.exec(delete(Order))
        db.exec(delete(Market))
        db.exec(delete(User))
        db.commit()
        return {"success": True, "message": "All data cleared."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database clear failed: {e}"
        )


@router.post(
    "/exec-sql",
    status_code=status.HTTP_200_OK,
    description="Execute arbitrary SQL (L2 only). Returns rows or affected row count.",
    dependencies=[Depends(require_l2)],
)
async def exec_sql(
    sql: str = Body(..., embed=True, description="SQL statement"),
    params: Optional[Dict[str, Any]] = Body(None, embed=True, description="Named parameters"),
    limit: int = Body(500, embed=True, description="Max rows to return for SELECT"),
    db: Session = Depends(get_session),
):
    try:
        stmt = text(sql)
        # Keep only bind params that actually exist in the statement
        if params:
            try:
                bound = set(stmt._bindparams.keys())  # public API
                params = {k: v for k, v in params.items() if k in bound} or None
            except Exception:
                params = None

        # bind params INTO the statement (fix)
        if params:
            stmt = stmt.bindparams(**params)

        sql_upper = sql.lstrip().upper()
        is_select = sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")

        if is_select:
            # No explicit transaction needed for a read
            result: Result = db.exec(stmt)
            rows = result.mappings().fetchmany(limit)
            keys = list(rows[0].keys()) if rows else list(result.keys())
            return {
                "columns": keys,
                "rows": [dict(r) for r in rows],
                "truncated": len(rows) == limit,
            }

        # Non-SELECT (DML/DDL) — run in a transaction and commit
        with db.begin():
            result: Result = db.exec(stmt)
        return {"affected_rows": result.rowcount}

    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("exec_sql failed")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL execution failed: {e}",
        )