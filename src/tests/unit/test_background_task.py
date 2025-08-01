import logging
import pytest
from contextlib import contextmanager

import src.background_task as bg
from src.services.market_sync_service import MarketSyncService, MarketSyncError
from src.services.resolution_service import ResolutionService, ResolutionError


# ensure INFO+ERROR level logs are captured
@pytest.fixture(autouse=True)
def caplog_info_level(caplog):
    caplog.set_level(logging.INFO)
    return caplog


def test_run_market_sync_with_no_winners(monkeypatch, caplog_info_level):
    """
    If sync_markets returns no 'winners', then resolution is never called,
    and we only see the sync commit.
    """
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
        lambda session: {"added_tracked": [], "removed_tracked": [], "winners": []}
    )
    # spy on the resolution call
    called = {"resolve": False}
    monkeypatch.setattr(
        ResolutionService,
        "resolve_market_winners",
        lambda db, winners: called.update(resolve=True)
    )

    bg.run_market_sync()

    # only the first commit should happen
    assert calls == ["commit"]
    assert "Market sync succeeded" in caplog_info_level.text
    assert not called["resolve"]


def test_run_market_sync_with_winners_and_resolution_success(monkeypatch, caplog_info_level):
    """
    If sync_markets returns winners, resolution should be called,
    and we should see two commits and the payout log.
    """
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
        lambda session: {"winners": [{"condition_id": "X"}]}
    )

    monkeypatch.setattr(
        ResolutionService,
        "resolve_market_winners",
        lambda db, winners: [{"market": "X", "num_payouts":0, "payouts":[], "total_paid":"0", "errors":[]}]
    )

    bg.run_market_sync()

    # two commits: one after sync, one after resolution
    assert calls == ["commit", "commit"]
    assert "Market sync succeeded" in caplog_info_level.text
    assert "Payouts resolved" in caplog_info_level.text


def test_run_market_sync_resolution_error(monkeypatch, caplog_info_level):
    """
    If resolution throws ResolutionError, ensure we rollback and log it.
    """
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
        lambda session: {"winners": [{"condition_id": "X"}]}
    )

    def raise_res_err(db, winners):
        raise ResolutionError("resolve_stage", RuntimeError("fail"))
    monkeypatch.setattr(ResolutionService, "resolve_market_winners", raise_res_err)

    bg.run_market_sync()

    # commit from sync, then rollback from resolution error
    assert calls == ["commit", "rollback"]
    assert "Market sync succeeded" in caplog_info_level.text
    assert "[resolve_stage] fail" in caplog_info_level.text
    assert "fail" in caplog_info_level.text


def test_run_market_sync_sync_error(monkeypatch, caplog_info_level):
    """
    If sync_markets throws MarketSyncError, ensure we rollback and log it,
    and resolution is never called.
    """
    calls = []
    class DummySession:
        def commit(self):    calls.append("commit")
        def rollback(self):  calls.append("rollback")

    @contextmanager
    def fake_context():
        yield DummySession()
    monkeypatch.setattr(bg, "get_session_context", fake_context)

    def raise_sync_err(session):
        raise MarketSyncError("sync_stage", RuntimeError("oops"))
    monkeypatch.setattr(MarketSyncService, "sync_markets", raise_sync_err)

    # Spy to ensure resolution is never called
    monkeypatch.setattr(
        ResolutionService,
        "resolve_market_winners",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("should not be called"))
    )

    # Run
    bg.run_market_sync()

    # We should only have rolled back
    assert calls == ["rollback"]

    # Log message uses no quotes around stage
    assert "Market sync failed at stage sync_stage: oops" in caplog_info_level.text






