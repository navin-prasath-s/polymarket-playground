from decimal import Decimal

import pytest
from sqlalchemy.future import select

from src.services.resolution_service import ResolutionService, ResolutionError
from src.models.user_position import UserPosition
from src.models.user import User
from src.models.payout_log import PayoutLog

def test_fetch_positions_returns_only_matching(db_session):
    # Arrange: three positions, two for market 'C1', one for 'C2'
    db_session.add_all([
        UserPosition(user_name="U1", market="C1", token="T1", shares=10),
        UserPosition(user_name="U2", market="C1", token="T2", shares=5),
        UserPosition(user_name="U3", market="C2", token="T3", shares=8),
    ])
    db_session.commit()

    # Act
    positions = ResolutionService._fetch_positions(db_session, "C1")

    # Assert: only U1 and U2 returned
    assert len(positions) == 2
    user_name = {pos.user_name for pos in positions}
    assert user_name == {"U1", "U2"}
    # Ensure the other position is not included
    assert all(pos.market == "C1" for pos in positions)


def test_fetch_positions_empty(db_session):
    # Arrange: no positions for market 'XYZ'
    db_session.commit()

    # Act
    positions = ResolutionService._fetch_positions(db_session, "XYZ")

    # Assert: returns an empty list
    assert positions == []


def test_fetch_user_profiles_returns_mapping(db_session, monkeypatch):
    # prepare a fake list of User objects
    fake_users = [
        User(name="Alice", balance=0),
        User(name="Bob", balance=100),
    ]

    # make session.exec(...) return a fake result whose .scalars().all() yields our fake_users
    class FakeResult:
        def scalars(self):
            return self
        def all(self):
            return fake_users

    monkeypatch.setattr(db_session, "exec", lambda stmt: FakeResult())

    # call with a set of the two names
    result = ResolutionService._fetch_user_profiles(db_session, {"Alice", "Bob"})

    assert set(result.keys()) == {"Alice", "Bob"}
    assert result["Alice"] is fake_users[0]
    assert result["Bob"] is fake_users[1]


def test_fetch_user_profiles_empty(db_session):
    # empty input should return empty dict without querying
    result = ResolutionService._fetch_user_profiles(db_session, set())
    assert result == {}



def test_process_position_winner(db_session):
    # Arrange: one user and one winning position
    user = User(name="alice", balance=Decimal("10.00"))
    pos = UserPosition(user_name="alice", market="MKT", token="TKN", shares=Decimal("5.00"))
    db_session.add_all([user, pos])
    db_session.commit()

    # Reload the position from the DB
    pos_db = db_session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).scalar_one()

    # Build the profiles map and winning set
    user_profiles = {"alice": user}
    winning_tokens = {"TKN"}

    # Act
    payout_log_obj = ResolutionService._process_position(
        db_session, pos_db, user_profiles, winning_tokens
    )
    db_session.commit()

    # Assert return values
    assert payout_log_obj.shares_paid == Decimal("5.00")
    assert payout_log_obj.is_winner is True
    assert payout_log_obj.user_name == "alice"


    # Assert user balance was updated
    updated_user = db_session.exec(
        select(User).where(User.name == "alice")
    ).scalar_one()
    assert updated_user.balance == Decimal("15.00")

    # Assert a PayoutLog was created
    log = db_session.exec(
        select(PayoutLog).where(PayoutLog.user_name == "alice")
    ).scalar_one()
    assert log.market == "MKT"
    assert log.token == "TKN"
    assert log.shares_paid == Decimal("5.00")
    assert log.is_winner is True

    # Assert the position was deleted
    remaining = db_session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).all()
    assert remaining == []


def test_process_position_non_winner(db_session):
    # Arrange: one user and one non-winning position
    user = User(name="bob", balance=Decimal("20.00"))
    pos = UserPosition(user_name="bob", market="MKT", token="TKN", shares=Decimal("5.00"))
    db_session.add_all([user, pos])
    db_session.commit()

    pos_db = db_session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).scalar_one()

    user_profiles = {"bob": user}
    winning_tokens: set[str] = set()

    # Act
    payout_log_obj = ResolutionService._process_position(
        db_session, pos_db, user_profiles, winning_tokens
    )
    db_session.commit()

    # Assert return values
    assert payout_log_obj.shares_paid == Decimal("0")
    assert payout_log_obj.is_winner is False

    # Assert user balance unchanged
    updated_user = db_session.exec(
        select(User).where(User.name == "bob")
    ).scalar_one()
    assert updated_user.balance == Decimal("20.00")

    # Assert a PayoutLog was created with zero shares_paid
    log = db_session.exec(
        select(PayoutLog).where(PayoutLog.user_name == "bob")
    ).scalar_one()
    assert log.shares_paid == Decimal("0")
    assert log.is_winner is False

    # Assert the position was deleted
    remaining = db_session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).all()
    assert remaining == []

