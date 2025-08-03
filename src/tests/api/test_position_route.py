import logging
from decimal import Decimal

from src.models.user import User
from src.models.user_position import UserPosition
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select

from src.app import app
from src.sessions import get_session


logging.basicConfig(level=logging.DEBUG)


def test_get_user_positions_empty(client, db_session):
    # Create the user but don’t give them any positions
    client.post("/users/", json={"name": "eve"})
    response = client.get("/positions/eve")
    assert response.status_code == 200
    assert response.json() == []

def test_get_user_positions_user_not_found(client, db_session):
    # No user “ghost” exists
    response = client.get("/positions/ghost")
    assert response.status_code == 404

def test_get_user_positions_with_data(client, db_session):
    # 1) create user
    client.post("/users/", json={"name": "frank"})
    # 2) seed two positions
    db_session.add_all([
        UserPosition(user_name="frank", market="mkt1", token="t1", shares=Decimal("10")),
        UserPosition(user_name="frank", market="mkt2", token="t2", shares=Decimal("0.50")),
    ])
    db_session.commit()
    # 3) call endpoint
    response = client.get("/positions/frank")
    assert response.status_code == 200
    data = response.json()
    # ensure both entries come back (as strings, since JSON-encoded)
    assert {"market": "mkt1", "token": "t1", "shares": "10.00"} in data
    assert {"market": "mkt2", "token": "t2", "shares": "0.50"} in data
    assert len(data) == 2

def test_get_all_positions_happy_path(client, db_session):
    db_session.query(UserPosition).delete()
    db_session.query(User).delete()
    db_session.commit()

    # Create users and positions
    db_session.add_all([
        User(name="alice", balance=0),
        User(name="bob", balance=0),
        UserPosition(user_name="alice", market="m1", token="t1", shares=Decimal("1")),
        UserPosition(user_name="bob", market="m2", token="t2", shares=Decimal("2")),
    ])
    db_session.commit()
    response = client.get("/positions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert {"market": "m1", "token": "t1", "shares": "1.00"} in data
    assert {"market": "m2", "token": "t2", "shares": "2.00"} in data
    assert len(data) == 2