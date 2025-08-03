# import json
# import logging
# from decimal import Decimal
#
# import pytest
# from contextlib import contextmanager
#
# from sqlalchemy import select
#
# import src.background_task as bg
# from src.models.market import Market
# from src.models.market_change_log import MarketChangeLog, MarketChangeType
# from src.models.payout_log import PayoutLog
# from src.models.sync_hot_market import SyncHotMarket
# from src.models.user import User
# from src.models.user_position import UserPosition
# from src.services.clob_service import ClobService
# from src.services.market_sync_service import MarketSyncService, MarketSyncError
# from src.services.resolution_service import ResolutionService, ResolutionError
#
#
# # ensure INFO+ERROR level logs are captured
# @pytest.fixture(autouse=True)
# def caplog_info_level(caplog):
#     caplog.set_level(logging.INFO)
#     return caplog
#
#
#
#
# def test_run_market_sync_with_no_winners(monkeypatch, caplog_info_level):
#     """
#     If sync_markets returns no 'winners', then resolution is never called,
#     and we only see the sync commit.
#     """
#     calls = []
#     class DummySession:
#         def commit(self):    calls.append("commit")
#         def rollback(self):  calls.append("rollback")
#
#     @contextmanager
#     def fake_context():
#         yield DummySession()
#
#     monkeypatch.setattr(bg, "get_session_context", fake_context)
#     monkeypatch.setattr(
#         MarketSyncService,
#         "sync_markets",
#         lambda session: {"added_tracked": [], "removed_tracked": [], "winners": []}
#     )
#     # spy on the resolution call
#     called = {"resolve": False}
#     monkeypatch.setattr(
#         ResolutionService,
#         "resolve_market_winners",
#         lambda db, winners: called.update(resolve=True)
#     )
#
#     bg.run_market_sync()
#
#     # only the first commit should happen
#     assert calls == ["commit"]
#     assert "Market sync succeeded" in caplog_info_level.text
#     assert not called["resolve"]
#
#
# def test_run_market_sync_with_winners_and_resolution_success(monkeypatch, caplog_info_level):
#     """
#     If sync_markets returns winners, resolution should be called,
#     and we should see two commits and the payout log.
#     """
#     calls = []
#     class DummySession:
#         def commit(self):    calls.append("commit")
#         def rollback(self):  calls.append("rollback")
#
#     @contextmanager
#     def fake_context():
#         yield DummySession()
#     monkeypatch.setattr(bg, "get_session_context", fake_context)
#
#     monkeypatch.setattr(
#         MarketSyncService,
#         "sync_markets",
#         lambda session: {"winners": [{"condition_id": "X"}]}
#     )
#
#     monkeypatch.setattr(
#         ResolutionService,
#         "resolve_market_winners",
#         lambda db, winners: [{"market": "X", "num_payouts":0, "payouts":[], "total_paid":"0", "errors":[]}]
#     )
#
#     bg.run_market_sync()
#
#     # two commits: one after sync, one after resolution
#     assert calls == ["commit", "commit"]
#     assert "Market sync succeeded" in caplog_info_level.text
#     assert "Payouts resolved" in caplog_info_level.text
#
#
# def test_run_market_sync_resolution_error(monkeypatch, caplog_info_level):
#     """
#     If resolution throws ResolutionError, ensure we rollback and log it.
#     """
#     calls = []
#     class DummySession:
#         def commit(self):    calls.append("commit")
#         def rollback(self):  calls.append("rollback")
#
#     @contextmanager
#     def fake_context():
#         yield DummySession()
#     monkeypatch.setattr(bg, "get_session_context", fake_context)
#
#     monkeypatch.setattr(
#         MarketSyncService,
#         "sync_markets",
#         lambda session: {"winners": [{"condition_id": "X"}]}
#     )
#
#     def raise_res_err(db, winners):
#         raise ResolutionError("resolve_stage", RuntimeError("fail"))
#     monkeypatch.setattr(ResolutionService, "resolve_market_winners", raise_res_err)
#
#     bg.run_market_sync()
#
#     # commit from sync, then rollback from resolution error
#     assert calls == ["commit", "rollback"]
#     assert "Market sync succeeded" in caplog_info_level.text
#     assert "[resolve_stage] fail" in caplog_info_level.text
#     assert "fail" in caplog_info_level.text
#
#
# def test_run_market_sync_sync_error(monkeypatch, caplog_info_level):
#     """
#     If sync_markets throws MarketSyncError, ensure we rollback and log it,
#     and resolution is never called.
#     """
#     calls = []
#     class DummySession:
#         def commit(self):    calls.append("commit")
#         def rollback(self):  calls.append("rollback")
#
#     @contextmanager
#     def fake_context():
#         yield DummySession()
#     monkeypatch.setattr(bg, "get_session_context", fake_context)
#
#     def raise_sync_err(session):
#         raise MarketSyncError("sync_stage", RuntimeError("oops"))
#     monkeypatch.setattr(MarketSyncService, "sync_markets", raise_sync_err)
#
#     # Spy to ensure resolution is never called
#     monkeypatch.setattr(
#         ResolutionService,
#         "resolve_market_winners",
#         lambda *args, **kwargs: (_ for _ in ()).throw(Exception("should not be called"))
#     )
#
#     # Run
#     bg.run_market_sync()
#
#     # We should only have rolled back
#     assert calls == ["rollback"]
#
#     # Log message uses no quotes around stage
#     assert "Market sync failed at stage sync_stage: oops" in caplog_info_level.text
#
#
#
#
#
# def test_run_market_sync_end_to_end_closes_market(session, monkeypatch, caplog_info_level):
#     # ─── Seed users and positions ───────────────────────────────────────────────
#     alice = User(name="alice", balance=Decimal("100"))
#     bob   = User(name="bob",   balance=Decimal("200"))
#     session.add_all([alice, bob])
#     session.add_all([
#         UserPosition(user_name="alice", market="MKT", token="YES", shares=Decimal("10")),
#         UserPosition(user_name="bob",   market="MKT", token="YES", shares=Decimal("5")),
#         UserPosition(user_name="bob",   market="MKT", token="NO",  shares=Decimal("20")),
#     ])
#     session.add(
#         SyncHotMarket(
#             condition_id="MKT",
#             question="Q",
#             description="D",
#             tokens=json.dumps(["YES","NO"])
#         )
#     )
#     session.add(Market(condition_id="MKT", is_tradable=True))
#     session.commit()
#
#     # ─── Stub CLOB so that no live markets => MKT is removed/closed ────────────
#     monkeypatch.setattr(
#         ClobService,
#         "get_clob_markets_accepting_orders",
#         lambda self: []
#     )
#     # When marking winners, simulate that YES won
#     monkeypatch.setattr(
#         ClobService,
#         "get_clob_market_by_condition_id",
#         staticmethod(lambda cid: {
#             "tokens": [
#                 {"token_id": "YES", "winner": True},
#                 {"token_id": "NO",  "winner": False},
#             ]
#         })
#     )
#
#     # ─── Use our test session in run_market_sync ───────────────────────────────
#     @contextmanager
#     def fake_ctx():
#         yield session
#     monkeypatch.setattr(bg, "get_session_context", fake_ctx)
#
#     # ─── Act ───────────────────────────────────────────────────────────────────
#     bg.run_market_sync()
#
#     # ─── Assert balances (resolution should run) ────────────────────────────────
#     balances = {u.name: u.balance for u in session.exec(select(User)).scalars()}
#     assert balances["alice"] == Decimal("110")  # +10
#     assert balances["bob"]   == Decimal("205")  # +5
#
#     # ─── Positions deleted ──────────────────────────────────────────────────────
#     assert session.exec(select(UserPosition)).all() == []
#
#     # ─── PayoutLog entries ──────────────────────────────────────────────────────
#     logs = session.exec(select(PayoutLog)).scalars().all()
#     winners = [l for l in logs if l.is_winner]
#     assert {(l.user_name, l.shares_paid) for l in winners} == {
#         ("alice", Decimal("10")),
#         ("bob",   Decimal("5")),
#     }
#
#     # ─── Hot table updated ───────────────────────────────────────────────────────
#     hot_ids = {m.condition_id for m in session.exec(select(SyncHotMarket)).scalars()}
#     assert "MKT" not in hot_ids
#
#     # ─── Stable market untradable ───────────────────────────────────────────────
#     m = session.exec(select(Market).where(Market.condition_id=="MKT")).scalar_one()
#     assert m.is_tradable is False
#
#     # ─── Change log recorded deletion ───────────────────────────────────────────
#     changes = {(c.condition_id, c.change_type) for c in session.exec(select(MarketChangeLog)).scalars()}
#     assert (("MKT", MarketChangeType.DELETED) in changes)
#
#     # ─── And logs show both sync + payout messages ─────────────────────────────
#     text = caplog_info_level.text
#     assert "Market sync succeeded" in text
#     assert "Payouts resolved" in text
#
#
#
#
