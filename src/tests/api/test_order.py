from decimal import Decimal

import pytest
from sqlmodel import select

from src.models.order import OrderType, OrderSide, OrderStatus
from src.models.user_position import UserPosition
from src.models.order import Order
from src.models.order_fill import OrderFill
from src.models.user import User
from src.models.market import Market
from src.models.market_outcome import MarketOutcome
from src.services.order_service import OrderService
from src.services.clob_service import ClobService


@pytest.fixture
def setup_data(db_session):
    user = User(
        name="user_buy",
        balance=Decimal("1000.00"),
    )
    db_session.add(user)
    db_session.flush()

    market = Market(
        condition_id="condition_buy",
        is_tradable=True
    )
    db_session.add(market)
    db_session.flush()

    market1_outcome1 = MarketOutcome(
        market="condition_buy",
        token="token_buy_1",
        outcome_text="Outcome 1"
    )
    market1_outcome2 = MarketOutcome(
        market="condition_buy",
        token="token_buy_2",
        outcome_text="Outcome 2"
    )
    db_session.add(market1_outcome1)
    db_session.add(market1_outcome2)
    db_session.commit()

    return {
        "user_name": user.name,
        "market_condition_id": market.condition_id,
        "market1_token1": market1_outcome1.token,
        "market1_token2": market1_outcome2.token,
    }

@pytest.fixture
def seed_after_buy(db_session):
    user = User(
        name="user_sell",
        balance=Decimal("800.00"),
    )
    db_session.add(user)
    db_session.flush()

    position = UserPosition(
        user_name="user_sell",
        market="condition_sell",
        token="token_sell_1",
        shares=Decimal("1750.00"),
    )
    db_session.add(position)

    market = Market(
        condition_id="condition_sell",
        is_tradable=True,
    )
    db_session.add(market)

    outcome = MarketOutcome(
        market="condition_sell",
        token="token_sell_1",
        outcome_text="Outcome 1"
    )
    db_session.add(outcome)
    db_session.commit()


def test_create_market_buy_order_new_share_success(
    client, db_session, setup_data, monkeypatch
):
    monkeypatch.setattr(
        ClobService,
        "get_book_by_token_id",
        staticmethod(lambda token, side: [])
    )
    monkeypatch.setattr(
        OrderService,
        "simulate_buy_transaction",
        staticmethod(lambda amount, book: {
            'status': 'filled',
            'shares_filled': Decimal("1750.00"),
            'total_cost': Decimal("200.00"),
            'fills': [
                {'fill_price': Decimal("0.1"), 'fill_shares': Decimal("1500.0")},
                {'fill_price': Decimal("0.2"), 'fill_shares': Decimal("250.0")},
            ]
        })
    )

    payload = {
        "user_name": setup_data["user_name"],
        "market": setup_data["market_condition_id"],
        "token": setup_data["market1_token1"],
        "order_type": OrderType.MARKET.value,
        "amount_usdc": "200.00",
    }
    response = client.post("/orders/buy", json=payload)
    assert response.status_code == 201
    body = response.json()

    assert body["status"] == "success"
    assert "order_id" in body
    assert Decimal(body["details"]["amount_usdc"]) == Decimal("200.00")
    assert Decimal(str(body["details"]["shares"])) == Decimal("1750.00")
    assert Decimal(body["details"]["average_price"]) == Decimal("200.00") / Decimal("1750.00")
    assert body["details"]["fills"] == 2

    # DB side effects
    user = db_session.exec(
        select(User).where(User.name == setup_data["user_name"])
    ).one()
    assert user.balance == Decimal("800.00")

    position = db_session.exec(
        select(UserPosition).where(
            UserPosition.user_name == setup_data["user_name"],
            UserPosition.market == setup_data["market_condition_id"],
            UserPosition.token == setup_data["market1_token1"]
        )
    ).one()
    assert position.shares == Decimal("1750.00")

    order_record = db_session.exec(
        select(Order).where(
            Order.user_name == setup_data["user_name"],
            Order.market == setup_data["market_condition_id"],
            Order.token == setup_data["market1_token1"]
        )
    ).one()
    assert order_record.side == OrderSide.BUY
    assert order_record.order_type == OrderType.MARKET
    assert order_record.status == OrderStatus.FILLED
    assert order_record.amount_usdc == Decimal("200.00")
    assert order_record.shares == Decimal("1750.00")

    fills = list(db_session.exec(
        select(OrderFill).where(OrderFill.order_id == order_record.order_id)
    ))
    assert len(fills) == 2


def test_create_market_sell_order_partial_success(
    client, db_session, seed_after_buy, monkeypatch
):
    fills = [
        {'fill_price': Decimal("0.15"), 'fill_shares': Decimal("500.0")},
        {'fill_price': Decimal("0.2"),  'fill_shares': Decimal("250.0")},
    ]
    total_proceeds = (Decimal("500.0") * Decimal("0.15")) + (Decimal("250.0") * Decimal("0.2"))  # 75 + 50 = 125

    monkeypatch.setattr(
        OrderService,
        "simulate_sell_transaction",
        staticmethod(lambda shares, book: {
            'status': 'filled',
            'shares_sold': Decimal("750.00"),
            'total_proceeds': total_proceeds,
            'fills': fills
        })
    )

    payload = {
        "user_name": "user_sell",
        "market": "condition_sell",
        "token": "token_sell_1",
        "order_type": OrderType.MARKET.value,
        "shares": "750.00"
    }
    response = client.post("/orders/sell", json=payload)
    assert response.status_code == 201
    body = response.json()

    assert body["status"] == "success"
    assert "order_id" in body
    assert Decimal(body["details"]["amount_usdc"]) == total_proceeds
    assert Decimal(str(body["details"]["shares"])) == Decimal("750.00")
    assert Decimal(body["details"]["average_price"]) == total_proceeds / Decimal("750.00")
    assert body["details"]["fills"] == 2

    user = db_session.exec(
        select(User).where(User.name == "user_sell")
    ).one()
    assert user.balance == Decimal("800.00") + total_proceeds

    position = db_session.exec(
        select(UserPosition).where(
            UserPosition.user_name == "user_sell",
            UserPosition.market == "condition_sell",
            UserPosition.token == "token_sell_1"
        )
    ).one()
    assert position.shares == Decimal("1000.00")

    order_record = db_session.exec(
        select(Order).where(
            Order.user_name == "user_sell",
            Order.market == "condition_sell",
            Order.token == "token_sell_1",
            Order.side == OrderSide.SELL
        )
    ).one()
    assert order_record is not None
    assert order_record.side == OrderSide.SELL
    assert order_record.order_type == OrderType.MARKET
    assert order_record.status == OrderStatus.FILLED
    assert order_record.amount_usdc == total_proceeds
    assert order_record.shares == Decimal("750.00")

    fill_objs = list(db_session.exec(
        select(OrderFill).where(OrderFill.order_id == order_record.order_id)
    ))
    assert len(fill_objs) == 2
    assert fill_objs[0].fill_price == Decimal("0.15")
    assert fill_objs[0].fill_shares == Decimal("500.0")
    assert fill_objs[1].fill_price == Decimal("0.2")
    assert fill_objs[1].fill_shares == Decimal("250.0")

