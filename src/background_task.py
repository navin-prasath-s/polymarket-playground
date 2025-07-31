import logging

from src.sessions import get_session_context
from src.services.market_sync_service import MarketSyncService
from src.services.market_sync_service import MarketSyncError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def run_market_sync():
    """
    Entry point for the background market synchronization task.
    Opens a session, runs the full sync pipeline, and commits or rolls back.
    """
    with get_session_context() as session:
        try:
            result = MarketSyncService.sync_markets(session)
            session.commit()
            logger.info("Market sync succeeded: %s", result)
        except MarketSyncError as e:
            session.rollback()
            logger.exception(
                "Market sync failed at stage '%s': %s",
                e.stage,
                e.original
            )
        except Exception as e:
            session.rollback()
            logger.exception("Unexpected error during market sync: %s", e)


if __name__ == "__main__":
    run_market_sync()

