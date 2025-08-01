# import pytest
# from sqlmodel import SQLModel, create_engine, Session
# from contextlib import contextmanager
#
#
# import src.sessions as sessions
# import src.models.market
# import src.models.sync_hot_market
# import src.models.market_outcome
# import src.models.market_change_log
# import src.models.user
# import src.models.user_position
# import src.models.order
# import src.models.order_fill
# import src.models.payout_log
#
#
# @pytest.fixture(scope="function")
# def engine():
#     """
#     Create a single in-memory SQLite engine for tests,
#     and override the one in src.sessions.
#     """
#     test_engine = create_engine("sqlite:///:memory:", echo=False)
#     SQLModel.metadata.create_all(test_engine)
#
#     # override the module‐level engine in your sessions.py
#     sessions.engine = test_engine
#
#     return test_engine
#
# @pytest.fixture(scope="function")
# def session(engine):
#     """
#     Yields a fresh Session per test and rolls back afterwards.
#     """
#     with Session(engine) as sess:
#         yield sess
#         sess.rollback()
#
# @pytest.fixture(autouse=True)
# def override_sessions_getters(session, monkeypatch):
#     """
#     Monkey‐patch both get_session (FastAPI DI) and get_session_context
#     to always yield our test 'session' fixture.
#     """
#     # FastAPI dependency
#     def _get_session_override() -> Session:
#         yield session
#     monkeypatch.setattr(sessions, "get_session", _get_session_override)
#
#     # Context-manager helper
#     @contextmanager
#     def _get_session_context_override():
#         yield session
#     monkeypatch.setattr(sessions, "get_session_context", _get_session_context_override)
#


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

from src.app import app
from src.sessions import get_session

from src.models.market import Market
from src.models.market_change_log import MarketChangeLog
from src.models.market_outcome import MarketOutcome
from src.models.sync_hot_market import SyncHotMarket
from src.models.order import Order
from src.models.order_fill import OrderFill
from src.models.payout_log import PayoutLog
from src.models.user import User
from src.models.user_position import UserPosition


# In-memory SQLite engine
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,           # ← use SQLModel’s Session
    expire_on_commit=False,   # optional but usually helpful
)

# Create/drop tables once per session
@pytest.fixture(scope="session", autouse=True)
def init_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

# Transactional session per test
@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session
    session.close()
    transaction.rollback()
    connection.close()

# Override FastAPI dependency for TestClient
@pytest.fixture()
def client(db_session):
    def _get_test_session():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_session] = _get_test_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

