from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from sqlalchemy.future import select

from src.models.market import Market
from src.models.market_change_log import MarketChangeLog, MarketChangeType
from src.models.market_outcome import MarketOutcome
from src.models.sync_hot_market import SyncHotMarket
from src.services.clob_service import ClobService



class MarketSyncService:

    @staticmethod
    def get_hot_sync_markets(db: Session) -> list[SyncHotMarket]:
        result = db.exec(select(SyncHotMarket))
        return result.all()


    @staticmethod
    def get_stable_markets(db: Session) -> list[Market]:
        result = db.exec(select(Market))
        return result.all()


    @staticmethod
    def add_tracked_markets(db: Session, markets: list) -> list[str]:
        """Add to TrackedMarket and log."""
        added_ids = []
        for market in markets:
            try:
                model_obj = SyncHotMarket(**market)
                db.add(model_obj)
                db.add(MarketChangeLog(
                    condition_id=model_obj.condition_id,
                    change_type=MarketChangeType.ADDED
                ))
                db.commit()
                added_ids.append(model_obj.condition_id)
            except IntegrityError:
                db.rollback()
            except Exception as e:
                db.rollback()
                print(f"Insert failed for {market['condition_id']}: {e}")
        return added_ids


    @staticmethod
    def remove_tracked_markets(db: Session, tracked_markets, removed_ids) -> list[str]:
        """Remove from TrackedMarket and log."""
        removed_ids_list = []
        for m in tracked_markets:
            if m.condition_id in removed_ids:
                try:
                    db.delete(m)
                    db.add(MarketChangeLog(
                        condition_id=m.condition_id,
                        change_type=MarketChangeType.DELETED
                    ))
                    db.commit()
                    removed_ids_list.append(m.condition_id)
                except Exception as e:
                    db.rollback()
                    print(f"Delete failed for {m.condition_id}: {e}")
        return removed_ids_list


    @staticmethod
    def add_stable_markets(db: Session, markets: list) -> list[str]:
        """Add new stable markets to Market table."""
        added_ids = []
        for market in markets:
            try:
                model_obj = Market(**market)
                db.add(model_obj)
                db.commit()
                added_ids.append(model_obj.condition_id)
            except IntegrityError:
                db.rollback()
            except Exception as e:
                db.rollback()
                print(f"Stable market insert failed for {market['condition_id']}: {e}")
        return added_ids


    @staticmethod
    def mark_markets_untradable(db: Session, condition_ids: list[str]) -> list[str]:
        """Set is_tradable = False in Market table."""
        updated_ids = []
        result = db.execute(select(Market).where(Market.condition_id.in_(condition_ids)))
        markets = result.scalars().all()
        for market in markets:
            market.is_tradable = False
            db.add(market)
            updated_ids.append(market.condition_id)
        db.commit()
        return updated_ids


    @staticmethod
    def add_market_outcomes(db: Session, markets: list[dict]) -> list[str]:
        """Insert outcomes for newly added stable markets"""
        inserted_keys = []
        for market in markets:
            market_id = market["condition_id"]
            for token_info in market.get("tokens", []):
                try:
                    obj = MarketOutcome(
                        market=market_id,
                        token=token_info["token_id"],
                        outcome_text=token_info.get("outcome")
                    )
                    db.add(obj)
                    inserted_keys.append(f"{market_id}:{token_info['token_id']}")
                except Exception as e:
                    print(f"Failed to insert outcome for {market_id}/{token_info['token_id']}: {e}")
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print(f"Failed to commit outcomes for market {market_id}: {e}")
        return inserted_keys

    @staticmethod
    def mark_market_outcome_winner(db: Session, resolved_markets: list[str]) -> list[dict]:
        """Mark outcomes as winners for resolved markets."""
        updated = []
        for condition_id in resolved_markets:
            market_info = ClobService.get_clob_market_by_condition_id(condition_id)
            tokens = market_info.get("tokens", [])
            winning_token_ids = [t["token_id"] for t in tokens if t.get("winner")]
            if not winning_token_ids:
                print(f"No winner found for market {condition_id}")
                continue

            try:
                result = db.execute(
                    select(MarketOutcome).where(
                        MarketOutcome.market == condition_id,
                        MarketOutcome.token.in_(winning_token_ids)
                    )
                )
                outcomes = result.scalars().all()
                for outcome in outcomes:
                    outcome.is_winner = True
                db.commit()

                updated.append({
                    "condition_id": condition_id,
                    "winning_token_ids": winning_token_ids,
                })

            except Exception as e:
                db.rollback()
                print(f"Failed to mark winner for market {condition_id}: {e}")

        return updated


    @staticmethod
    def sync_markets(db: Session) -> dict:
        # 1. Get all live CLOB markets
        clob_markets = ClobService().get_clob_markets_accepting_orders()
        clob_condition_ids = {market['condition_id'] for market in clob_markets}

        # 2. Get all current tracked (hot DB) markets
        tracked_markets = MarketSyncService.get_hot_sync_markets(db)
        tracked_condition_ids = {m.condition_id for m in tracked_markets}

        # 3. Get all current stable (main) markets
        stable_markets = MarketSyncService.get_stable_markets(db)
        stable_condition_ids = {m.condition_id for m in stable_markets}

        # 4. Find diffs
        newly_added = clob_condition_ids - tracked_condition_ids
        removed = tracked_condition_ids - clob_condition_ids

        # 5. Add new tracked markets
        to_add = [m for m in clob_markets if m["condition_id"] in newly_added]
        added_tracked = MarketSyncService.add_tracked_markets(db, to_add)

        # 6. Remove tracked markets
        removed_tracked = MarketSyncService.remove_tracked_markets(db, tracked_markets, removed)

        # 7. Add to stable market DB (if not present)
        new_for_stable = [m for m in clob_markets if
                          m["condition_id"] in newly_added and m["condition_id"] not in stable_condition_ids]
        added_stable = MarketSyncService.add_stable_markets(db, new_for_stable)

        # 8. Add outcomes for the newly stable markets
        just_added_markets = [m for m in clob_markets if m["condition_id"] in added_stable]
        outcomes_inserted = MarketSyncService.add_market_outcomes(db, just_added_markets)

        # 9. Mark removed as untradable in market DB
        marked_untradable = MarketSyncService.mark_markets_untradable(db, list(removed))

        # 10. Mark outcomes as winners
        winners =  MarketSyncService.mark_market_outcome_winner(db, marked_untradable)

        return {
            "added_tracked": added_tracked,
            "removed_tracked": removed_tracked,
            "added_stable": added_stable,
            "outcomes_inserted": outcomes_inserted,
            "marked_untradable": marked_untradable,
            "winners": winners
        }


# TODO: Make no commits here and make the api route handle the commit/rollback