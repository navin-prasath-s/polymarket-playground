import pytest
from decimal import Decimal

from sqlmodel import select

from src.models.user import User
from src.models.market import Market
from src.models.market_outcome import MarketOutcome
from src.models.user_position import UserPosition
from src.models.order import Order, OrderStatus, OrderType, OrderSide
from src.models.order_fill import OrderFill
from src.services.clob_service import ClobService
from src.services.order_service import OrderService


@pytest.fixture(autouse=True)
def stub_clob_and_order(monkeypatch):
    # stub CLOB lookup
    monkeypatch.setattr(
        ClobService,
        "get_book_by_token_id",
        staticmethod(lambda token, side: []),
    )
    # stub buy simulation
    monkeypatch.setattr(
        OrderService,
        "simulate_buy_transaction",
        staticmethod(lambda amount, book: {
            "total_cost":    Decimal("100.00"),
            "shares_filled": Decimal("10"),
            "fills": [
                {"fill_price": Decimal("10.00"), "fill_shares": Decimal("10")},
            ]
        }),
    )
    # stub sell simulation
    monkeypatch.setattr(
        OrderService,
        "simulate_sell_transaction",
        staticmethod(lambda shares, book: {
            "total_proceeds": Decimal("100.00"),
            "shares_sold":    Decimal("10"),
            "fills": [
                {"fill_price": Decimal("10.00"), "fill_shares": Decimal("10")},
            ]
        }),
    )
    monkeypatch.setattr(
        OrderService,
        "simulate_sell_transaction",
        staticmethod(lambda shares, book: {
            "total_proceeds": Decimal("100.00"),
            "shares_sold": Decimal("10"),
            "fills": [
                {"fill_price": Decimal("10.00"), "fill_shares": Decimal("10")},
            ]
        }),
    )


def test_create_buy_order_happy_path(client, db_session):
    # Seed DB: user, market, outcome
    user    = User(name="alice", balance=Decimal("1000.00"))
    market  = Market(condition_id="m1", is_tradable=True)
    outcome = MarketOutcome(market="m1", token="t1")
    db_session.add_all([user, market, outcome])
    db_session.commit()

    payload = {
        "user_name":   "alice",
        "market":      "m1",
        "token":       "t1",
        "order_type":  OrderType.MARKET.value,
        "amount_usdc": "100.00",
    }
    response = client.post("/orders/buy", json=payload)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["status"] == "success"
    assert Decimal(body["details"]["amount_usdc"]) == Decimal("100.00")
    assert Decimal(str(body["details"]["shares"])) == Decimal("10")
    assert abs(Decimal(body["details"]["average_price"]) - Decimal("10.00")) < Decimal("0.0001")
    assert body["details"]["fills"] == 1

    # Verify DB side-effects
    refreshed = db_session.exec(
        select(User).where(User.name == "alice")
    ).one()
    assert refreshed.balance == Decimal("900.00")

    pos = db_session.exec(
        select(UserPosition)
        .where(
            UserPosition.user_name == "alice",
            UserPosition.market    == "m1",
            UserPosition.token     == "t1",
        )
    ).one()
    assert pos.shares == Decimal("10")

    order_row = db_session.exec(
        select(Order).where(
            Order.user_name == "alice",
            Order.side      == OrderSide.BUY
        )
    ).one()
    assert order_row.status == OrderStatus.FILLED
    assert order_row.shares == Decimal("10")

    fill = db_session.exec(
        select(OrderFill).where(OrderFill.order_id == order_row.order_id)
    ).one()
    assert fill.fill_price  == Decimal("10.00")
    assert fill.fill_shares == Decimal("10")


def test_create_sell_order_happy_path(client, db_session):
    # Use a different user to avoid unique constraint collision
    user     = User(name="bob", balance=Decimal("1000.00"))
    market   = Market(condition_id="m2", is_tradable=True)
    outcome  = MarketOutcome(market="m2", token="t1")
    position = UserPosition(user_name="bob", market="m2", token="t1", shares=Decimal("20"))
    db_session.add_all([user, market, outcome, position])
    db_session.commit()

    payload = {
        "user_name":  "bob",
        "market":     "m2",
        "token":      "t1",
        "order_type": OrderType.MARKET.value,
        "shares":     "10",
    }
    response = client.post("/orders/sell", json=payload)
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["status"] == "success"
    assert Decimal(body["details"]["amount_usdc"]) == Decimal("100.00")
    assert Decimal(str(body["details"]["shares"])) == Decimal("10")
    assert abs(Decimal(body["details"]["average_price"]) - Decimal("10.00")) < Decimal("0.0001")
    assert body["details"]["fills"] == 1

    # Verify DB side-effects
    refreshed = db_session.exec(
        select(User).where(User.name == "bob")
    ).one()
    assert refreshed.balance == Decimal("1100.00")

    pos = db_session.exec(
        select(UserPosition)
        .where(
            UserPosition.user_name == "bob",
            UserPosition.market    == "m2",
            UserPosition.token     == "t1"
        )
    ).one()
    assert pos.shares == Decimal("10")

    order_row = db_session.exec(
        select(Order).where(
            Order.user_name == "bob",
            Order.side      == OrderSide.SELL
        )
    ).one()
    assert order_row.status == OrderStatus.FILLED
    assert order_row.shares == Decimal("10")
    assert order_row.amount_usdc == Decimal("100.00")

    fill = db_session.exec(
        select(OrderFill).where(OrderFill.order_id == order_row.order_id)
    ).one()
    assert fill.fill_price  == Decimal("10.00")
    assert fill.fill_shares == Decimal("10")



def test_list_all_orders_happy_path(client, db_session):
    # seed two orders for different users
    order1 = Order(
        user_name="alice",
        market="m1",
        token="t1",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        amount_usdc=Decimal("100.00"),
        shares=Decimal("10")
    )
    order2 = Order(
        user_name="bob",
        market="m2",
        token="t2",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        amount_usdc=Decimal("50.00"),
        shares=Decimal("5")
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    response = client.get("/orders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert {o["user_name"] for o in data} == {"alice", "bob"}


def test_list_orders_for_user_happy_path(client, db_session):
    db_session.add(User(name="alicee", balance=Decimal("0.00")))
    order1 = Order(
        user_name="alicee",
        market="m1",
        token="t1",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        amount_usdc=Decimal("100.00"),
        shares=Decimal("10")
    )
    order2 = Order(
        user_name="bobb",
        market="m2",
        token="t2",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        amount_usdc=Decimal("50.00"),
        shares=Decimal("5")
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    response = client.get("/orders/alicee")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["user_name"] == "alicee"
    assert data[0]["market"] == "m1"


def test_get_all_orders_happy_path(client, db_session):
    db_session.query(Order).delete()
    db_session.query(User).delete()
    db_session.commit()
    db_session.add(User(name="alicee22", balance=Decimal("0.00")))
    db_session.add(User(name="bobb22", balance=Decimal("0.00")))
    order1 = Order(
        user_name="alicee22",
        market="m1",
        token="t1",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        amount_usdc=Decimal("100.00"),
        shares=Decimal("10")
    )
    order2 = Order(
        user_name="bobb22",
        market="m2",
        token="t2",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        amount_usdc=Decimal("50.00"),
        shares=Decimal("5")
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    response = client.get("/orders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    user_names = {d["user_name"] for d in data}
    assert "alicee22" in user_names
    assert "bobb22" in user_names
