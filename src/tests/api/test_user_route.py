import logging
import os
from decimal import Decimal

from dotenv import load_dotenv
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select

from src.app import app
from src.models.user_position import UserPosition
from src.sessions import get_session


logging.basicConfig(level=logging.DEBUG)


load_dotenv()
L1_KEY = os.getenv("L1_KEY")
L2_KEY = os.getenv("L2_KEY")


def test_create_user_happy_path(client, db_session):
    payload = {"name": "alicee2", "balance": "100.00"}
    response = client.post("/users/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alicee2"
    assert Decimal(data["balance"]) == Decimal("100.00")


def test_create_user_no_balance(client, db_session):
    payload = {"name": "alicea"}
    response = client.post("/users/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alicea"
    assert Decimal(data["balance"]) == Decimal("10000.00")


def test_create_user_missing_payload(client):
    response = client.post("/users/", json={})
    assert response.status_code == 422  # Unprocessable Entity for missing required 'name'


@pytest.mark.parametrize("user_name, balance_body, expected_balance", [
    ("bob", {"balance": "500.00"}, Decimal("500.00")),
    ("bob2", {}, Decimal("10000.00")),
])
def test_reset_user_with_and_without_balance(client, db_session, user_name, balance_body, expected_balance):
    # First, create the user
    client.post("/users/", json={"name": user_name})
    # PATCH request to new endpoint
    response = client.patch(
        f"/users/{user_name}/reset-balance",
        json=balance_body,
        headers={"X-API-Key": L1_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == user_name
    assert Decimal(data["balance"]) == expected_balance

def test_reset_user_wrong_key(client, db_session):
    # Create user
    client.post("/users/", json={"name": "charlie"})
    headers = {"X-API-Key": "wrong-key"}
    payload = {"balance": "100.00"}
    response = client.patch("/users/charlie/reset-balance", json=payload, headers=headers)
    assert response.status_code == 403

def test_reset_user_no_key(client, db_session):
    # Create user
    client.post("/users/", json={"name": "dave"})
    payload = {"balance": "100.00"}
    response = client.patch("/users/dave/reset-balance", json=payload)
    assert response.status_code == 403

