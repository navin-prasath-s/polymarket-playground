from decimal import Decimal

import pytest
from sqlalchemy.future import select
from sqlmodel import Session

from src.services.resolution_service import ResolutionService, ResolutionError
from src.models.user_position import UserPosition
from src.models.user import User
from src.models.payout_log import PayoutLog

def test_fetch_positions_returns_only_matching(session: Session):
    # Arrange: three positions, two for market 'C1', one for 'C2'
    session.add_all([
        UserPosition(user_name="U1", market="C1", token="T1", shares=10),
        UserPosition(user_name="U2", market="C1", token="T2", shares=5),
        UserPosition(user_name="U3", market="C2", token="T3", shares=8),
    ])
    session.commit()

    # Act
    positions = ResolutionService._fetch_positions(session, "C1")

    # Assert: only U1 and U2 returned
    assert len(positions) == 2
    user_name = {pos.user_name for pos in positions}
    assert user_name == {"U1", "U2"}
    # Ensure the other position is not included
    assert all(pos.market == "C1" for pos in positions)


def test_fetch_positions_empty(session: Session):
    # Arrange: no positions for market 'XYZ'
    session.commit()

    # Act
    positions = ResolutionService._fetch_positions(session, "XYZ")

    # Assert: returns an empty list
    assert positions == []


def test_fetch_user_profiles_returns_mapping(session, monkeypatch):
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

    monkeypatch.setattr(session, "exec", lambda stmt: FakeResult())

    # call with a set of the two names
    result = ResolutionService._fetch_user_profiles(session, {"Alice", "Bob"})

    assert set(result.keys()) == {"Alice", "Bob"}
    assert result["Alice"] is fake_users[0]
    assert result["Bob"] is fake_users[1]


def test_fetch_user_profiles_empty(session):
    # empty input should return empty dict without querying
    result = ResolutionService._fetch_user_profiles(session, set())
    assert result == {}



def test_process_position_winner(session: Session):
    # Arrange: one user and one winning position
    user = User(name="alice", balance=Decimal("10.00"))
    pos = UserPosition(user_name="alice", market="MKT", token="TKN", shares=Decimal("5.00"))
    session.add_all([user, pos])
    session.commit()

    # Reload the position from the DB
    pos_db = session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).scalar_one()

    # Build the profiles map and winning set
    user_profiles = {"alice": user}
    winning_tokens = {"TKN"}

    # Act
    payout_amount, payout_entry, errors = ResolutionService._process_position(
        session, pos_db, user_profiles, winning_tokens
    )
    session.commit()

    # Assert return values
    assert payout_amount == Decimal("5.00")
    assert payout_entry == {"user_name": "alice", "shares_paid": "5.00"}
    assert errors == []

    # Assert user balance was updated
    updated_user = session.exec(
        select(User).where(User.name == "alice")
    ).scalar_one()
    assert updated_user.balance == Decimal("15.00")

    # Assert a PayoutLog was created
    log = session.exec(
        select(PayoutLog).where(PayoutLog.user_name == "alice")
    ).scalar_one()
    assert log.market == "MKT"
    assert log.token == "TKN"
    assert log.shares_paid == Decimal("5.00")
    assert log.is_winner is True

    # Assert the position was deleted
    remaining = session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).all()
    assert remaining == []


def test_process_position_non_winner(session: Session):
    # Arrange: one user and one non-winning position
    user = User(name="bob", balance=Decimal("20.00"))
    pos = UserPosition(user_name="bob", market="MKT", token="TKN", shares=Decimal("5.00"))
    session.add_all([user, pos])
    session.commit()

    pos_db = session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).scalar_one()

    user_profiles = {"bob": user}
    winning_tokens: set[str] = set()

    # Act
    payout_amount, payout_entry, errors = ResolutionService._process_position(
        session, pos_db, user_profiles, winning_tokens
    )
    session.commit()

    # Assert return values
    assert payout_amount == Decimal("0")
    assert payout_entry is None
    assert errors == []

    # Assert user balance unchanged
    updated_user = session.exec(
        select(User).where(User.name == "bob")
    ).scalar_one()
    assert updated_user.balance == Decimal("20.00")

    # Assert a PayoutLog was created with zero shares_paid
    log = session.exec(
        select(PayoutLog).where(PayoutLog.user_name == "bob")
    ).scalar_one()
    assert log.shares_paid == Decimal("0")
    assert log.is_winner is False

    # Assert the position was deleted
    remaining = session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).all()
    assert remaining == []


def test_process_position_no_profile(session: Session):
    # Arrange: position exists but no profile in map
    pos = UserPosition(user_name="ghost", market="MKT", token="TKN", shares=Decimal("5.00"))
    session.add(pos)
    session.commit()
    pos_db = session.exec(select(UserPosition).where(UserPosition.market == "MKT")).scalar_one()

    # Act: pass empty profiles dict, token is winning
    payout_amount, payout_entry, errors = ResolutionService._process_position(
        session, pos_db, {}, {"TKN"}
    )
    session.commit()

    # Assert: log created, no exception, no payout_entry since profile missing
    assert payout_amount == Decimal("0")
    assert payout_entry is None
    assert errors == []
    log = session.exec(select(PayoutLog).where(PayoutLog.user_name=="ghost")).scalar_one()
    assert log.is_winner is True


def test_process_position_balance_update_error(session: Session):
    # Arrange: fake profile whose balance setter blows up
    class BadUser:
        def __init__(self):
            self._bal = Decimal("0")
        @property
        def balance(self):
            return self._bal
        @balance.setter
        def balance(self, value):
            raise RuntimeError("boom")

    bad = BadUser()
    pos = UserPosition(
        user_name="bob",
        market="MKT",
        token="TKN",
        shares=Decimal("5")
    )
    session.add_all([pos])
    session.commit()
    pos_db = session.exec(
        select(UserPosition).where(UserPosition.market == "MKT")
    ).scalar_one()

    # Act: bob is in winning_tokens, but setting balance will error
    payout_amount, payout_entry, errors = ResolutionService._process_position(
        session, pos_db, {"bob": bad}, {"TKN"}
    )
    session.commit()

    # Assert: we caught the balance‐update error, and payout_amount stays zero
    assert payout_amount == Decimal("0")
    assert payout_entry is None
    assert any("Failed to update balance for user bob" in e for e in errors)


def test_process_position_delete_error(session: Session, monkeypatch):
    # Arrange: normal winner, but db.delete blows up
    user = User(name="alice", balance=Decimal("0"))
    pos = UserPosition(user_name="alice", market="MKT", token="TKN", shares=Decimal("1"))
    session.add_all([user, pos])
    session.commit()
    pos_db = session.exec(select(UserPosition).where(UserPosition.market=="MKT")).scalar_one()

    # Monkey-patch .delete to raise
    monkeypatch.setattr(session, "delete", lambda x: (_ for _ in ()).throw(RuntimeError("nope")))

    # Act
    payout_amount, payout_entry, errors = ResolutionService._process_position(
        session, pos_db, {"alice": user}, {"TKN"}
    )
    session.commit()

    # Assert: the delete-error was caught
    assert payout_amount == Decimal("1")
    assert payout_entry == {
        "user_name": "alice",
        "shares_paid": str(Decimal("1.00"))
    }


def test_resolve_market_winners_success(monkeypatch, session):
    # Arrange: two markets that both succeed
    inputs = [{"condition_id": "A"}, {"condition_id": "B"}]
    outputs = [
        {"market": "A", "num_payouts": 1, "payouts": [], "total_paid": "0", "errors": []},
        {"market": "B", "num_payouts": 2, "payouts": [], "total_paid": "0", "errors": []},
    ]

    # Stub _process_single_market to return in-order outputs
    monkeypatch.setattr(
        ResolutionService,
        "_process_single_market",
        lambda db, wm: outputs.pop(0)
    )

    # Act
    result = ResolutionService.resolve_market_winners(session, list(inputs))

    # Assert
    assert result == [
        {"market": "A", "num_payouts": 1, "payouts": [], "total_paid": "0", "errors": []},
        {"market": "B", "num_payouts": 2, "payouts": [], "total_paid": "0", "errors": []},
    ]


def test_resolve_market_winners_error(monkeypatch, session):
    # Arrange: first market succeeds, second one raises
    markets = [{"condition_id": "A"}, {"condition_id": "B"}]

    def fake_process(db, wm):
        if wm["condition_id"] == "A":
            return {"market": "A", "num_payouts": 0, "payouts": [], "total_paid": "0", "errors": []}
        else:
            raise RuntimeError("boom")

    monkeypatch.setattr(ResolutionService, "_process_single_market", fake_process)

    # Act & Assert
    with pytest.raises(ResolutionError) as excinfo:
        ResolutionService.resolve_market_winners(session, markets)

    err = excinfo.value
    assert err.stage == "resolve_market_winners"
    assert isinstance(err.original, RuntimeError)
    assert "boom" in str(err.original)


