import logging
import pytest
from contextlib import contextmanager

import src.background_task as bg
from src.services.market_sync_service import MarketSyncService, MarketSyncError

# auto-capture INFO+ERROR logs
@pytest.fixture(autouse=True)
def caplog_info_level(caplog):
    caplog.set_level(logging.INFO)
    return caplog


def test_run_market_sync_success(monkeypatch, caplog_info_level):
    calls = []
    class DummySession:
        def commit(self):    calls.append("commit")
        def rollback(self):  calls.append("rollback")

    @contextmanager
    def fake_context():
        yield DummySession()
    monkeypatch.setattr(bg, "get_session_context", fake_context)

    monkeypatch.setattr(
        MarketSyncService,
        "sync_markets",
        lambda session: {"foo": "bar"}
    )

    bg.run_market_sync()

    assert calls == ["commit"]
    assert "Market sync succeeded: {'foo': 'bar'}" in caplog_info_level.text


def test_run_market_sync_market_sync_error(monkeypatch, caplog_info_level):
    calls = []
    class DummySession:
        def commit(self):    calls.append("commit")
        def rollback(self):  calls.append("rollback")

    @contextmanager
    def fake_context():
        yield DummySession()
    monkeypatch.setattr(bg, "get_session_context", fake_context)

    def raise_sync_error(session):
        raise MarketSyncError("my_stage", RuntimeError("kaboom"))
    monkeypatch.setattr(MarketSyncService, "sync_markets", raise_sync_error)

    bg.run_market_sync()

    assert calls == ["rollback"]
    assert "Market sync failed at stage 'my_stage': kaboom" in caplog_info_level.text


def test_run_market_sync_unexpected_exception(monkeypatch, caplog_info_level):
    calls = []
    class DummySession:
        def commit(self):    calls.append("commit")
        def rollback(self):  calls.append("rollback")

    @contextmanager
    def fake_context():
        yield DummySession()
    monkeypatch.setattr(bg, "get_session_context", fake_context)

    def raise_value_error(session):
        raise ValueError("oops")
    monkeypatch.setattr(MarketSyncService, "sync_markets", raise_value_error)

    bg.run_market_sync()

    assert calls == ["rollback"]
    assert "Unexpected error during market sync: oops" in caplog_info_level.text
