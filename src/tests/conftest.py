# tests/conftest.py
import pytest
from sqlmodel import SQLModel, create_engine, Session
from contextlib import contextmanager


import src.session as sessions
import src.models.market
import src.models.sync_hot_market
import src.models.market_outcome
import src.models.market_change_log
import src.models.user
import src.models.user_position
import src.models.order
import src.models.order_fill
import src.models.payout_log


@pytest.fixture(scope="session")
def engine():
    """
    Create a single in-memory SQLite engine for tests,
    and override the one in src.sessions.
    """
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(test_engine)

    # override the module‐level engine in your sessions.py
    sessions.engine = test_engine

    return test_engine

@pytest.fixture
def session(engine):
    """
    Yields a fresh Session per test and rolls back afterwards.
    """
    with Session(engine) as sess:
        yield sess
        sess.rollback()

@pytest.fixture(autouse=True)
def override_sessions_getters(session, monkeypatch):
    """
    Monkey‐patch both get_session (FastAPI DI) and get_session_context
    to always yield our test 'session' fixture.
    """
    # FastAPI dependency
    def _get_session_override() -> Session:
        yield session
    monkeypatch.setattr(sessions, "get_session", _get_session_override)

    # Context-manager helper
    @contextmanager
    def _get_session_context_override():
        yield session
    monkeypatch.setattr(sessions, "get_session_context", _get_session_context_override)
