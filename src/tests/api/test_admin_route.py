import logging
import os
from decimal import Decimal

from dotenv import load_dotenv
from sqlmodel import select

from src.models.user import User

logging.basicConfig(level=logging.DEBUG)


load_dotenv()
L1_KEY = os.getenv("L1_KEY")
L2_KEY = os.getenv("L2_KEY")


def test_clear_all_data_deletes_users(client, db_session):
    # Add a user to the DB
    db_session.add(User(name="testuser", balance=Decimal("123")))
    db_session.commit()

    # Confirm the user exists before clear
    users_before = db_session.exec(select(User)).all()
    assert any(u.name == "testuser" for u in users_before)

    # Call the clear-all endpoint (must provide valid L2 key)
    response = client.delete("/admin/clear-all", headers={"X-API-Key": L2_KEY})
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Now check user table is empty
    users_after = db_session.exec(select(User)).all()
    assert users_after == []