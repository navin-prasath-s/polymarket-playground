import logging

from src.sessions import get_session_context
from src.market_event_webhook import emit_market_event, MarketEventType
from src.services.market_sync_service import MarketSyncService, MarketSyncError
from src.services.resolution_service import ResolutionService, ResolutionError

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)



def run_market_sync():
    """
    Entry point for the background market synchronization task.
    Opens a session, runs the full sync pipeline, and commits or rolls back.
    """
    logger.info("Market sync job started")
    with get_session_context() as session:
        try:
            # 1) sync markets
            result = MarketSyncService.sync_markets(session)
            session.commit()
            logger.info(f"Market sync succeeded: {result}", )

            # 1.1) Emit added markets to webhook
            added_markets = result.get("added_dict_model", [])
            emit_market_event(
                MarketEventType.MARKET_ADDED.value,
                {"markets": added_markets}
            )

            # 2) resolve payouts for any removed/untradable markets
            markets_with_winning_tokens = result.get("markets_with_winning_tokens", [])
            payout_logs = []
            if markets_with_winning_tokens:
                payout_logs = ResolutionService.resolve_market_winners(session, markets_with_winning_tokens)
                session.commit()
                logger.info(f"Payouts resolved: {payout_logs}", )

            # 2.1) Emit resolved markets to webhook
            emit_market_event(
                MarketEventType.MARKET_RESOLVED.value,
                {"markets": markets_with_winning_tokens}
            )

            # 2.2) Emit payout logs to webhook
            emit_market_event(
                MarketEventType.PAYOUT_LOGS.value,
                {"payout_logs": payout_logs}
            )

        except MarketSyncError as e:
            session.rollback()
            logger.exception(
                f"Market sync failed at stage {e.stage}: {e.original}"
            )
        except ResolutionError as e:
            session.rollback()
            logger.exception(
                f"Resolution failed at stage {e.stage} {e.original}"
            )
        except Exception as e:
            session.rollback()
            logger.exception(f"Unexpected error during market sync: {e}")

    logger.info("Market sync job ended")

