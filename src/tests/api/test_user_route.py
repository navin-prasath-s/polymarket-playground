import logging
import os
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session, select

from src.app import app
from src.sessions import get_session
from src.models.user import User


logging.basicConfig(level=logging.DEBUG)


load_dotenv()
L1_KEY = os.getenv("L1_KEY")
L2_KEY = os.getenv("L2_KEY")


def test_create_user_happy_path(client, db_session):
    payload = {"name": "alice", "balance": "100.00"}
    response = client.post("/users/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alice"
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


@pytest.mark.parametrize("balance_input, expected_balance", [
    ({"name": "bob", "balance": "500.00"}, Decimal("500.00")),
    ({"name": "bob2"}, Decimal("10000.00")),
])
def test_reset_user_with_and_without_balance(client, db_session, balance_input, expected_balance):
    # First, create the user to reset
    client.post("/users/", json={"name": balance_input["name"]})
    # Perform reset
    response = client.patch(
        "/users/reset-user",
        json=balance_input,
        headers={"X-API-Key": L1_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == balance_input["name"]
    assert Decimal(data["balance"]) == expected_balance

def test_reset_user_wrong_key(client, db_session):
    # Create user
    client.post("/users/", json={"name": "charlie"})
    headers = {"X-API-Key": "wrong-key"}
    payload = {"name": "charlie", "balance": "100.00"}
    response = client.patch("/users/reset-user", json=payload, headers=headers)
    assert response.status_code == 403

def test_reset_user_no_key(client, db_session):
    # Create user
    client.post("/users/", json={"name": "dave"})
    payload = {"name": "dave", "balance": "100.00"}
    response = client.patch("/users/reset-user", json=payload)
    assert response.status_code == 403
