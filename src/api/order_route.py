import logging
from decimal import Decimal


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from src.models.order_fill import OrderFill
from src.models.user import User
from src.models.user_position import UserPosition
from src.services.clob_service import ClobService
from src.services.order_service import OrderService
from src.sessions import get_session
from src.models.market_outcome import MarketOutcome
from src.models.order import OrderBuyCreate, Order, OrderSide, OrderType, OrderStatus, OrderSellCreate, OrderRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders",
                   tags=["orders"])


@router.post("/buy",
                status_code=status.HTTP_201_CREATED,
                description="Create a new buy order.")
async def create_buy_order(
        order: OrderBuyCreate,
        db: Session = Depends(get_session),
) -> dict:

    # 1. Check if market and token exists in market_outcome db
    market_outcome_statement = (
        select(MarketOutcome)
        .options(selectinload(MarketOutcome.market_obj))
        .where(
            MarketOutcome.market == order.market,
            MarketOutcome.token == order.token
        )
    )
    market_outcome = db.exec(market_outcome_statement).one_or_none()
    if not market_outcome:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid market/token combination. Market '{order.market}' with token '{order.token}' not found."
        )

    # 2. Check if market is active
    if not market_outcome.market_obj.is_tradable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Market '{order.market}' is not tradable at this time."
        )


    # 3. Fetch the user and their balance
    user = db.exec(select(User).where(User.name == order.user_name)).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User user_profile not found"
        )

    # 4. Check if the user has sufficient balance
    if user.balance < order.amount_usdc:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient funds. Your balance is {user.balance}, but order requires {order.amount_usdc}."
        )

    # 5. Simulate the order
    asks_book = ClobService.get_book_by_token_id(order.token, side="BUY")
    result = OrderService.simulate_buy_transaction(
        amount=order.amount_usdc,
        book=asks_book,
    )

    # 6. If exceeds liquidity
    if result.get("status") == "exceeds_liquidity":
        raise HTTPException(
            status_code=400,
            detail=f"Order exceeds liquidity. "
                   f"Max amount you can buy is {result['max_amount']} USDC and Max shares is {result['max_shares']}."
        )

    total_cost = result.get("total_cost")
    total_shares = result.get("shares_filled")
    fills = result.get("fills")

    # 7. Commit to db
    try:
        # 7a. Update user_profile balance
        user.balance -= total_cost

        # 7b. Upsert UserPosition table
        user_position_statement = select(UserPosition).where(
            UserPosition.user_name == user.name,
            UserPosition.market == order.market,
            UserPosition.token == order.token
        )
        existing_position = db.exec(user_position_statement).one_or_none()

        if existing_position:
            existing_position.shares += total_shares
        else:
            new_position = UserPosition(
                user_name=user.name,
                market=order.market,
                token=order.token,
                shares=total_shares
            )
            db.add(new_position)

        # 7c. Create Order
        new_order = Order(
            user_name=user.name,
            market=order.market,
            token=order.token,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            amount_usdc=total_cost,
            shares=total_shares,
        )
        db.add(new_order)
        db.flush()

        # 7d. Create OrderFill
        for fill in fills:
            order_fill = OrderFill(
                order_id=new_order.order_id,
                fill_price=fill['fill_price'],
                fill_shares=fill['fill_shares'],
            )
            db.add(order_fill)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the order: {str(e)}"
        )


    return {
        "status": "success",
        "details": {
            "amount_usdc": total_cost,
            "shares": total_shares,
            "average_price": total_cost / total_shares,
            "fills": len(fills)
        }
    }


@router.post(
    "/sell",
    status_code=status.HTTP_201_CREATED,
    description="Create a new sell order.",
)
def create_sell_order(
    order: OrderSellCreate,
    db: Session = Depends(get_session),
) -> dict:
    # 1. Verify market/token exists
    mo_stmt = (
        select(MarketOutcome)
        .options(selectinload(MarketOutcome.market_obj))
        .where(
            MarketOutcome.market == order.market,
            MarketOutcome.token == order.token,
        )
    )
    mo = db.exec(mo_stmt).one_or_none()
    if not mo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Invalid market/token. "
                f"Market '{order.market}', token '{order.token}' not found."
            ),
        )

    # 2. Must be tradable
    if not mo.market_obj.is_tradable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Market '{order.market}' is not tradable right now.",
        )

    # 3. Fetch user & their position
    user = db.exec(
        select(User).where(User.name == order.user_name)
    ).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    up_stmt = select(UserPosition).where(
        UserPosition.user_name == user.name,
        UserPosition.market == order.market,
        UserPosition.token == order.token,
    )
    user_pos = db.exec(up_stmt).one_or_none()
    if not user_pos or user_pos.shares < order.shares:
        have = user_pos.shares if user_pos else Decimal("0")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient shares: you have {have}, "
                f"tried to sell {order.shares}."
            ),
        )

    # 4. Simulate
    bids = ClobService.get_book_by_token_id(order.token, side="SELL")
    result = OrderService.simulate_sell_transaction(
        shares=order.shares,
        book=bids,
    )

    # 5. Liquidity check
    if result.get("status") == "exceeds_liquidity":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Exceeds liquidity: max shares {result['max_shares']}, "
                f"worth {result['max_amount']} USDC."
            ),
        )

    proceeds = result["total_proceeds"]
    sold = result["shares_sold"]
    fills = result["fills"]

    # 6. Persist
    try:
        # a) credit user balance
        user.balance += proceeds

        # b) debit their position
        user_pos.shares -= sold

        # c) create Order
        new_order = Order(
            user_name=user.name,
            market=order.market,
            token=order.token,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            amount_usdc=proceeds,
            shares=sold,
        )
        db.add(new_order)
        db.flush()  # populate new_order.order_id

        # d) record fills
        for f in fills:
            db.add(OrderFill(
                order_id=new_order.order_id,
                fill_price = f["fill_price"],
                fill_shares= f["fill_shares"],
            ))

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing sell: {e}"
        )

    return {
        "status":   "success",
        "details": {
            "amount_usdc":  proceeds,
            "shares":       sold,
            "average_price": (proceeds / sold) if sold else None,
            "fills":         len(fills),
        },
    }


@router.get(
    "/",
    response_model=list[OrderRead],
    status_code=status.HTTP_200_OK,
    description="Get all the orders.",
)
async def get_all_orders(
    db: Session = Depends(get_session),
):
    try:
        orders = db.exec(select(Order).options(selectinload(Order.fills))).all()
        return orders
    except Exception as e:
        logger.error(f"Failed to fetch orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching orders."
        )


@router.get(
    "/{user_name}",
    response_model=list[OrderRead],
    status_code=status.HTTP_200_OK,
    description="Get all orders placed by a particular user."
)
async def get_user_orders(
    user_name: str,
    db: Session = Depends(get_session),
):
    # Optionally check if user exists
    if not db.exec(select(User).where(User.name == user_name)).one_or_none():
        raise HTTPException(404, "user not found")
    orders = db.exec(select(Order).where(Order.user_name == user_name)).all()
    return orders


@router.get(
    "/",
    response_model=list[OrderRead],
    status_code=status.HTTP_200_OK,
    description="Get all orders in the system."
)
async def get_all_orders(
    db: Session = Depends(get_session),
):
    orders = db.exec(select(Order)).all()
    return orders