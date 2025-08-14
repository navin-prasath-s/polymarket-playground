import json
import logging
from collections import defaultdict

from sqlmodel import Session
from sqlalchemy.future import select

from src.models.market import Market
from src.models.market_change_log import MarketChangeLog, MarketChangeType
from src.models.market_outcome import MarketOutcome
from src.models.sync_hot_market import SyncHotMarket
from src.services.clob_service import ClobService

logger = logging.getLogger(__name__)


class MarketSyncError(Exception):
    def __init__(self, stage: str, original: Exception):
        super().__init__(f"[{stage}] {original}")
        self.stage = stage
        self.original = original



class MarketSyncService:

    @staticmethod
    def get_hot_sync_markets(db: Session) -> list[SyncHotMarket]:
        """
        Load all currently tracked (hot) markets from the DB.
        Raises MarketSyncError on failure.
        """
        try:
            result = db.exec(select(SyncHotMarket))
            return result.scalars().all()
        except Exception as e:
            logger.exception("Error fetching hot sync markets")
            raise MarketSyncError("get_hot_sync_markets", e)



    @staticmethod
    def get_stable_markets(db: Session) -> list[Market]:
        """
        Load all stable markets from the DB.
        Raises MarketSyncError on failure.
        """
        try:
            result = db.exec(select(Market))
            return result.scalars().all()
        except Exception as e:
            logger.exception("Error fetching stable markets")
            raise MarketSyncError("get_stable_markets", e)

    @staticmethod
    def add_hot_sync_markets(db: Session, markets: list[dict]) -> tuple[list[str], list[dict]]:
        """
        Stage new SyncHotMarket rows + change logs, skipping any
        condition_ids that already exist.
        """
        added_ids: list[str] = []
        added_dicts: list[dict] = []
        existing = {m.condition_id for m in db.exec(select(SyncHotMarket)).scalars()}

        for mkt in markets:
            cid = mkt["condition_id"]
            if cid in existing:
                continue

            try:
                outcome_texts = [t.get("outcome") for t in mkt.get("tokens", [])]

                model_obj = SyncHotMarket(
                    condition_id=cid,
                    question=mkt["question"],
                    description=mkt["description"],
                    tokens=json.dumps(outcome_texts),
                )
                db.add(model_obj)

                db.add(
                    MarketChangeLog(
                        condition_id=cid,
                        change_type=MarketChangeType.ADDED
                    )
                )

                added_ids.append(cid)
                added_dicts.append(model_obj.model_dump())

            except Exception as e:
                logger.exception(f"Unexpected error in add_hot_sync_markets for {cid}")
                raise MarketSyncError("add_hot_sync_markets", e)

        return added_ids, added_dicts



    @staticmethod
    def remove_hot_sync_markets(
            db: Session,
            tracked_markets: list[SyncHotMarket],
            removed_ids: list[str]
    ) -> list[str]:
        """
        Stage deletions of SyncHotMarket rows and their change logs.
        Raises MarketSyncError on failure.
        """
        removed_list: list[str] = []
        try:
            for m in tracked_markets:
                if m.condition_id in removed_ids:
                    db.delete(m)
                    db.add(
                        MarketChangeLog(
                            condition_id=m.condition_id,
                            change_type=MarketChangeType.DELETED
                        )
                    )
                    removed_list.append(m.condition_id)
            return removed_list

        except Exception as e:
            logger.exception("Error in remove_tracked_markets")
            raise MarketSyncError("remove_tracked_markets", e)



    @staticmethod
    def add_stable_markets(db: Session, markets: list[dict]) -> list[str]:
        """
        Stage new Market rows in the session.
        Raises MarketSyncError on failure.
        """
        try:
            added_ids: list[str] = []
            for mkt in markets:
                cid = mkt["condition_id"]
                model = Market(**mkt)
                db.add(model)
                added_ids.append(cid)
            return added_ids

        except Exception as e:
            logger.exception("Error in add_stable_markets")
            raise MarketSyncError("add_stable_markets", e)



    @staticmethod
    def mark_stable_markets_untradable(db: Session, condition_ids: list[str]) -> list[str]:
        """
        Stage updating `is_tradable=False` on existing Market rows.
        Raises MarketSyncError on failure.
        """
        try:
            updated_ids: list[str] = []
            result = db.exec(
                select(Market).where(Market.condition_id.in_(condition_ids))
            )
            for market in result.scalars():
                market.is_tradable = False
                db.add(market)
                updated_ids.append(market.condition_id)
            return updated_ids

        except Exception as e:
            logger.exception("Error in mark_markets_untradable")
            raise MarketSyncError("mark_markets_untradable", e)

    @staticmethod
    def add_stable_market_outcomes(db: Session, markets: list[dict]) -> list[str]:
        try:
            with db.no_autoflush:
                desired = []  # list[(cid, token_id, outcome_text)]
                for m in markets:
                    cid = m["condition_id"]
                    for t in (m.get("tokens") or []):
                        tok = (t.get("token_id") or "").strip()
                        if not tok:
                            # you chose to skip empties; fine
                            logger.debug(f"Skipping empty token for market: {cid}")
                            continue
                        desired.append((cid, tok, (t.get("outcome") or "").strip() or None))

                if not desired:
                    return []

                by_market = defaultdict(list)
                for cid, tok, _ in desired:
                    by_market[cid].append(tok)

                existing: set[tuple[str, str]] = set()
                for cid, toks in by_market.items():
                    if not toks:
                        continue
                    rows = db.exec(
                        select(MarketOutcome.market, MarketOutcome.token)
                        .where(MarketOutcome.market == cid, MarketOutcome.token.in_(toks))
                    ).all()
                    existing.update(rows)

                to_insert = [(cid, tok, text) for (cid, tok, text) in desired if (cid, tok) not in existing]

                inserted_keys: list[str] = []
                for cid, tok, text in to_insert:
                    db.add(MarketOutcome(market=cid, token=tok, outcome_text=text))
                    inserted_keys.append(f"{cid}:{tok}")

                return inserted_keys

        except Exception as e:
            logger.exception("Error in add_market_outcomes")
            raise MarketSyncError("add_market_outcomes", e)



    @staticmethod
    def mark_market_outcome_winner(db: Session, resolved_markets: list[str]) -> list[dict]:
        """
        Stage marking winners on MarketOutcome entries in the session.
        Raises MarketSyncError on failure.
        """
        try:
            updated: list[dict] = []
            for cid in resolved_markets:
                market_info = ClobService.get_clob_market_by_condition_id(cid)
                tokens = market_info.get("tokens", [])
                winning_token_ids = [t["token_id"] for t in tokens if t.get("winner")]

                if not winning_token_ids:
                    continue

                result = db.exec(
                    select(MarketOutcome).where(
                        MarketOutcome.market == cid,
                        MarketOutcome.token.in_(winning_token_ids)
                    )
                )
                for outcome in result.scalars():
                    outcome.is_winner = True
                    db.add(outcome)

                updated.append({
                    "condition_id": cid,
                    "winning_token_ids": winning_token_ids,
                })

            return updated

        except Exception as e:
            logger.exception("Error in mark_market_outcome_winner")
            raise MarketSyncError("mark_market_outcome_winner", e)


    @staticmethod
    def sync_markets(db: Session) -> dict:
        """
        Fetch live CLOB markets, compute diffs, and stage all changes in the session.
        Raises MarketSyncError on failure.
        """
        # 1. Fetch live CLOB markets
        try:
            clob_markets = ClobService().get_clob_markets_accepting_orders()
        except Exception as e:
            logger.exception("Error fetching live CLOB markets")
            raise MarketSyncError("get_clob_markets_accepting_orders", e)
        clob_ids = {m["condition_id"] for m in clob_markets}

        # 2. Load tracked and stable from DB
        tracked = MarketSyncService.get_hot_sync_markets(db)
        tracked_ids = {m.condition_id for m in tracked}
        stable = MarketSyncService.get_stable_markets(db)
        stable_ids = {m.condition_id for m in stable}

        # 3. Compute diffs
        to_add = [m for m in clob_markets if m["condition_id"] not in tracked_ids]
        to_remove = [cid for cid in tracked_ids if cid not in clob_ids]

        # 4. Stage all changes
        added_tracked, added_dicts = MarketSyncService.add_hot_sync_markets(db, to_add)
        removed_tracked = MarketSyncService.remove_hot_sync_markets(db, tracked, to_remove)
        added_stable = MarketSyncService.add_stable_markets(
            db, [m for m in to_add if m["condition_id"] not in stable_ids]
        )
        outcomes_inserted = MarketSyncService.add_stable_market_outcomes(
            db, [m for m in clob_markets if m["condition_id"] in added_stable]
        )
        marked_untradable = MarketSyncService.mark_stable_markets_untradable(db, removed_tracked)
        markets_with_winning_tokens = MarketSyncService.mark_market_outcome_winner(db, marked_untradable)

        return {
            "added_tracked": added_tracked,
            "added_dict_model": added_dicts,
            "removed_tracked": removed_tracked,
            "added_stable": added_stable,
            "outcomes_inserted": outcomes_inserted,
            "marked_untradable": marked_untradable,
            "markets_with_winning_tokens": markets_with_winning_tokens,
        }

