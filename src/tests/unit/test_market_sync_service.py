import json

import pytest
from sqlalchemy.future import select
from sqlmodel import Session

from src.background_task import run_market_sync
from src.market_event_webhook import MarketEventType
from src.models.market_change_log import MarketChangeLog, MarketChangeType
from src.models.market_outcome import MarketOutcome
from src.models.sync_hot_market import SyncHotMarket
from src.models.market import Market
from src.services.clob_service import ClobService
from src.services.market_sync_service import MarketSyncService


def test_get_hot_sync_markets_returns_all(db_session):
    db_session.add_all([
        SyncHotMarket(
            condition_id="A",
            question="Q?",
            description="Desc",
            tokens="{YES, NO}",
        ),
        SyncHotMarket(
            condition_id="B",
            question="Q2?",
            description="Desc2",
            tokens="{YES, NO}",
        ),
    ])
    db_session.commit()

    tracked = MarketSyncService.get_hot_sync_markets(db_session)
    ids = {m.condition_id for m in tracked}
    questions = {m.question for m in tracked}
    assert ids == {"A", "B"}
    assert questions == {"Q?", "Q2?"}


def test_get_stable_markets_returns_all(db_session):
    db_session.add_all([
        Market(
            condition_id="X",
            is_tradable=True,
        ),
        Market(
            condition_id="Y",
            is_tradable=True,
        ),
    ])
    db_session.commit()

    # Act
    stable = MarketSyncService.get_stable_markets(db_session)

    # Assert
    ids = {m.condition_id for m in stable}
    assert ids == {"X", "Y"}


def test_add_tracked_markets_happy_path(db_session):
    # Arrange
    markets = [
        {
            "condition_id": "M1",
            "question": "Q1",
            "description": "D1",
            "tokens": [
                {"token_id": "t1", "outcome": "YES"},
                {"token_id": "t2", "outcome": "NO"},
            ],
        },
        {
            "condition_id": "M2",
            "question": "Q2",
            "description": "D2",
            "tokens": [
                {"token_id": "t3", "outcome": "YES"},
                {"token_id": "t4", "outcome": "NO"},
            ],
        },
    ]

    # Act
    added, _ = MarketSyncService.add_hot_sync_markets(db_session, markets)
    db_session.commit()

    # Assert return value
    assert set(added) == {"M1", "M2"}

    # Assert DB state
    rows = db_session.exec(select(SyncHotMarket)).scalars().all()
    assert {r.condition_id for r in rows} == {"M1", "M2"}

    logs = db_session.exec(select(MarketChangeLog)).scalars().all()
    assert len(logs) == 2
    for log in logs:
        assert log.change_type == MarketChangeType.ADDED
        assert log.condition_id in {"M1", "M2"}


def test_remove_tracked_markets_happy_path(db_session):
    # Arrange: insert two tracked markets
    m1 = SyncHotMarket(
        condition_id="M1",
        question="Q1",
        description="D1",
        tokens="[]",
    )
    m2 = SyncHotMarket(
        condition_id="M2",
        question="Q2",
        description="D2",
        tokens="[]",
    )
    db_session.add_all([m1, m2])
    db_session.commit()

    tracked = db_session.exec(select(SyncHotMarket)).scalars().all()

    # Act
    removed = MarketSyncService.remove_hot_sync_markets(
        db_session,
        tracked_markets=tracked,
        removed_ids=["M1"],
    )
    db_session.commit()

    # Assert return value
    assert removed == ["M1"]

    # Assert that only M2 remains
    remaining = db_session.exec(select(SyncHotMarket)).scalars().all()
    assert {m.condition_id for m in remaining} == {"M2"}

    # Assert a deletion log was created
    logs = db_session.exec(select(MarketChangeLog)).scalars().all()
    assert any(
        log.condition_id == "M1" and log.change_type == MarketChangeType.DELETED
        for log in logs
    )


def test_add_stable_markets_happy_path(db_session):
    # Arrange: two new markets
    markets = [
        {"condition_id": "S1"},
        {"condition_id": "S2"},
    ]

    # Act
    added = MarketSyncService.add_stable_markets(db_session, markets)
    db_session.commit()

    # Assert return value
    assert set(added) == {"S1", "S2"}

    # Assert DB state contains the new markets
    rows = db_session.exec(select(Market)).scalars().all()
    assert {m.condition_id for m in rows} == {"S1", "S2"}



def test_mark_markets_untradable_happy_path(db_session):
    # Arrange: two new stable markets
    m1 = Market(condition_id="T1")
    m2 = Market(condition_id="T2")
    db_session.add_all([m1, m2])
    db_session.commit()

    # Act
    updated = MarketSyncService.mark_stable_markets_untradable(db_session, ["T1"])
    db_session.commit()

    # Assert return value
    assert updated == ["T1"]

    # Assert DB state: T1 is now untradable, T2 remains tradable
    markets = db_session.exec(select(Market)).scalars().all()
    status_map = {m.condition_id: m.is_tradable for m in markets}
    assert status_map == {"T1": False, "T2": True}


def test_mark_market_outcome_winner_happy_path(db_session, monkeypatch):
    # Arrange: insert two MarketOutcome rows
    db_session.add_all([
        MarketOutcome(market="C1", token="T1", outcome_text="Yes"),
        MarketOutcome(market="C1", token="T2", outcome_text="No"),
    ])
    db_session.commit()

    # Mock ClobService to designate T2 as the winner
    def fake_get_clob(cid):
        return {"tokens": [
            {"token_id": "T1", "winner": False},
            {"token_id": "T2", "winner": True},
        ]}
    monkeypatch.setattr(
        "src.services.clob_service.ClobService.get_clob_market_by_condition_id",
        staticmethod(lambda cid: fake_get_clob(cid))
    )

    # Act
    updated = MarketSyncService.mark_market_outcome_winner(db_session, ["C1"])
    db_session.commit()

    # Assert return value
    assert updated == [{"condition_id": "C1", "winning_token_ids": ["T2"]}]

    # Assert DB state: T2 marked as winner, T1 remains False
    outcomes = db_session.exec(
        select(MarketOutcome).where(MarketOutcome.market == "C1")
    ).scalars().all()
    flag_map = {o.token: o.is_winner for o in outcomes}
    assert flag_map == {"T1": False, "T2": True}



def test_add_market_outcomes_happy_path(db_session):
    # Arrange: payload with two outcomes for a single market
    markets = [
        {
            "condition_id": "M42",
            "tokens": [
                {"token_id": "TK_A", "outcome": "Alpha"},
                {"token_id": "TK_B", "outcome": "Beta"},
            ]
        }
    ]

    # Act
    inserted = MarketSyncService.add_stable_market_outcomes(db_session, markets)
    db_session.commit()

    # Assert return value
    assert set(inserted) == {"M42:TK_A", "M42:TK_B"}

    # Assert DB state: two MarketOutcome rows were staged
    rows = db_session.exec(select(MarketOutcome)).scalars().all()
    keys = {f"{r.market}:{r.token}" for r in rows}
    assert keys == {"M42:TK_A", "M42:TK_B"}




def test_sync_markets_full_flow(db_session, monkeypatch):
    # ─── Arrange ────────────────────────────────────────────────────────────────
    # 1) initial HOT (will be removed)
    db_session.add(
        SyncHotMarket(
            condition_id="OLD",
            question="Q_old",
            description="D_old",
            tokens=json.dumps(["X", "Y"])
        )
    )
    # 2) initial STABLE markets:
    #    - OLD is tradable
    #    - KEEP is already untradable
    db_session.add_all([
        Market(condition_id="OLD", is_tradable=True),
        Market(condition_id="KEEP", is_tradable=False),
    ])
    # 3) initial MarketOutcome rows for OLD (will get a winner marked)
    db_session.add_all([
        MarketOutcome(market="OLD", token="T1", outcome_text="Yes"),
        MarketOutcome(market="OLD", token="T2", outcome_text="No"),
    ])
    db_session.commit()

    # Fake the CLOB “accepting orders” to return exactly one NEW market
    new_mkt = {
        "condition_id": "NEW",
        "question": "Q_new",
        "description": "D_new",
        "tokens": [
            {"token_id": "T1", "outcome": "Alpha"},
            {"token_id": "T2", "outcome": "Beta"},
        ],
    }
    monkeypatch.setattr(
        ClobService,
        "get_clob_markets_accepting_orders",
        lambda self: [new_mkt]
    )
    # Fake the per‐market fetch to say T1 is the winner for OLD
    monkeypatch.setattr(
        ClobService,
        "get_clob_market_by_condition_id",
        staticmethod(lambda cid: {
            "tokens": [
                {"token_id": "T1", "winner": True},
                {"token_id": "T2", "winner": False},
            ]
        })
    )

    # ─── Act ───────────────────────────────────────────────────────────────────
    result = MarketSyncService.sync_markets(db_session)
    db_session.commit()

    # ─── Assert return payload ─────────────────────────────────────────────────
    assert result["added_tracked"]     == ["NEW"]
    assert result["removed_tracked"]   == ["OLD"]
    assert result["added_stable"]      == ["NEW"]
    assert set(result["outcomes_inserted"]) == {"NEW:T1", "NEW:T2"}
    assert result["marked_untradable"] == ["OLD"]
    assert result["markets_with_winning_tokens"] == [{"condition_id": "OLD", "winning_token_ids": ["T1"]}]

    # ─── Assert DB state: sync_hot_markets ─────────────────────────────────────
    hot = db_session.exec(select(SyncHotMarket)).scalars().all()
    assert {h.condition_id for h in hot} == {"NEW"}

    # ─── Assert DB state: markets ──────────────────────────────────────────────
    mk = db_session.exec(select(Market)).scalars().all()
    tradable_map = {m.condition_id: m.is_tradable for m in mk}
    assert tradable_map == {
        "OLD": False,   # marked untradable
        "KEEP": False,  # left alone
        "NEW": True,    # newly added (default True)
    }

    # ─── Assert DB state: market_outcomes ─────────────────────────────────────
    outs = db_session.exec(select(MarketOutcome)).scalars().all()
    winner_flags = {(o.market, o.token): o.is_winner for o in outs}
    assert winner_flags == {
        ("OLD","T1"): True,   # winner marked
        ("OLD","T2"): False,
        ("NEW","T1"): False,  # new outcomes default to False
        ("NEW","T2"): False,
    }

    # ─── Assert DB state: change logs ─────────────────────────────────────────
    logs = db_session.exec(select(MarketChangeLog)).scalars().all()
    assert {(log.condition_id, log.change_type) for log in logs} == {
        ("NEW", MarketChangeType.ADDED),
        ("OLD", MarketChangeType.DELETED),
    }


def test_sync_markets_with_overlap(db_session, monkeypatch):
    # ─── Arrange ────────────────────────────────────────────────────────────────
    # 1) initial HOT: OLD (will be removed) and UNCH (should stay)
    db_session.add_all([
        SyncHotMarket(
            condition_id="OLD",
            question="Q_old",
            description="D_old",
            tokens=json.dumps(["X", "Y"])
        ),
        SyncHotMarket(
            condition_id="UNCH",
            question="Q_unch",
            description="D_unch",
            tokens=json.dumps(["A", "B"])
        ),
    ])

    # 2) initial STABLE markets:
    #    - OLD is tradable (to be untradable)
    #    - KEEP is already untradable (never touched)
    #    - UNCH is tradable (should remain so)
    db_session.add_all([
        Market(condition_id="OLD",  is_tradable=True),
        Market(condition_id="KEEP", is_tradable=False),
        Market(condition_id="UNCH", is_tradable=True),
    ])

    # 3) initial outcomes for OLD and UNCH
    db_session.add_all([
        MarketOutcome(market="OLD",   token="T1", outcome_text="Yes"),
        MarketOutcome(market="OLD",   token="T2", outcome_text="No"),
        MarketOutcome(market="UNCH",  token="U1", outcome_text="Foo"),
        MarketOutcome(market="UNCH",  token="U2", outcome_text="Bar"),
    ])

    db_session.commit()

    # 4) fake CLOB → one brand‐new plus the “unchanged” one
    new_mkt = {
        "condition_id": "NEW",
        "question": "Q_new",
        "description": "D_new",
        "tokens": [
            {"token_id": "N1", "outcome": "Alpha"},
            {"token_id": "N2", "outcome": "Beta"},
        ],
    }
    unchanged_mkt = {
        "condition_id": "UNCH",
        "question": "Q_unch",
        "description": "D_unch",
        "tokens": [
            {"token_id": "U1", "outcome": "Foo"},
            {"token_id": "U2", "outcome": "Bar"},
        ],
    }
    monkeypatch.setattr(
        ClobService,
        "get_clob_markets_accepting_orders",
        lambda self: [new_mkt, unchanged_mkt]
    )
    # Only OLD gets resolved to a winner
    monkeypatch.setattr(
        ClobService,
        "get_clob_market_by_condition_id",
        staticmethod(lambda cid: {
            "tokens": [
                {"token_id": "T1", "winner": True},
                {"token_id": "T2", "winner": False},
            ]
        })
    )

    # ─── Act ───────────────────────────────────────────────────────────────────
    result = MarketSyncService.sync_markets(db_session)
    db_session.commit()

    # ─── Assert return payload ─────────────────────────────────────────────────
    assert result["added_tracked"]     == ["NEW"]
    assert result["removed_tracked"]   == ["OLD"]
    assert result["added_stable"]      == ["NEW"]
    assert set(result["outcomes_inserted"]) == {"NEW:N1", "NEW:N2"}
    assert result["marked_untradable"] == ["OLD"]
    assert result["markets_with_winning_tokens"] == [{"condition_id": "OLD", "winning_token_ids": ["T1"]}]


    # ─── DB: sync_hot_markets ──────────────────────────────────────────────────
    hot = db_session.exec(select(SyncHotMarket)).scalars().all()
    assert {h.condition_id for h in hot} == {"NEW", "UNCH"}

    # ─── DB: markets ───────────────────────────────────────────────────────────
    mk = db_session.exec(select(Market)).scalars().all()
    trad_map = {m.condition_id: m.is_tradable for m in mk}
    assert trad_map == {
        "OLD":   False,  # was turned off
        "KEEP":  False,  # untouched
        "UNCH":  True,   # stayed on
        "NEW":   True,   # newly added
    }

    # ─── DB: market_outcomes ───────────────────────────────────────────────────
    outs = db_session.exec(select(MarketOutcome)).scalars().all()
    flags = {(o.market, o.token): o.is_winner for o in outs}
    # OLD’s T1 flipped, UNCH stays unchanged, NEW inserted (all False)
    assert flags == {
        ("OLD","T1"):   True,
        ("OLD","T2"):   False,
        ("UNCH","U1"):  False,
        ("UNCH","U2"):  False,
        ("NEW","N1"):   False,
        ("NEW","N2"):   False,
    }

    # ─── DB: change logs ────────────────────────────────────────────────────────
    logs = db_session.exec(select(MarketChangeLog)).scalars().all()
    assert {(l.condition_id, l.change_type) for l in logs} == {
        ("NEW", MarketChangeType.ADDED),
        ("OLD", MarketChangeType.DELETED),
    }


def test_market_added_event_emitted(monkeypatch, db_session):
    # Arrange: Add a new market (that will be "added" by sync)
    mkt = SyncHotMarket(
        condition_id="MTEST",
        question="Test Q",
        description="Test D",
        tokens='["Yes", "No"]'
    )
    db_session.add(mkt)
    db_session.commit()

    # Prepare to capture emitted events

    emitted = []
    def fake_emit_market_event(event_type, payload):
        print(f"FAKE CALLED! {event_type=}, {payload=}")
        emitted.append((event_type, payload))

    monkeypatch.setattr(
        "src.background_task.emit_market_event", fake_emit_market_event
    )

    # Monkeypatch MarketSyncService.sync_markets to return a fake result
    monkeypatch.setattr(
        "src.services.market_sync_service.MarketSyncService.sync_markets",
        staticmethod(lambda session: {
            "added_dict_model": [mkt.model_dump()],
            "added_tracked": ["MTEST"],
            "removed_tracked": [],
            "added_stable": [],
            "outcomes_inserted": [],
            "marked_untradable": [],
            "markets_with_winning_tokens": [],
        })
    )

    # Act
    run_market_sync()

    # Assert: Was emit_market_event called as expected?
    assert emitted[0][0] == MarketEventType.MARKET_ADDED.value
    assert emitted[1][0] == MarketEventType.MARKET_RESOLVED.value
    assert emitted[2][0] == MarketEventType.PAYOUT_LOGS.value

    expected_added = {'markets': [mkt.model_dump()]}
    expected_resolved = {'markets': []}
    expected_payouts = {'payout_logs': []}

    assert emitted[0][1] == expected_added
    assert emitted[1][1] == expected_resolved
    assert emitted[2][1] == expected_payouts
