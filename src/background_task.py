import logging

from src.sessions import get_session_context
from src.services.market_sync_service import MarketSyncService, MarketSyncError
from src.services.resolution_service import ResolutionService, ResolutionError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# TODO: use BackgroundTasks from fast api to run this in the background

def run_market_sync():
    """
    Entry point for the background market synchronization task.
    Opens a session, runs the full sync pipeline, and commits or rolls back.
    """
    with get_session_context() as session:
        try:
            # 1) sync markets
            result = MarketSyncService.sync_markets(session)
            session.commit()
            logger.info(f"Market sync succeeded: {result}", )

            # 2) resolve payouts for any removed/untradable markets
            winners = result.get("winners", [])
            if winners:
                payouts = ResolutionService.resolve_market_winners(session, winners)
                session.commit()
                logger.info(f"Payouts resolved: {payouts}", )

            # combined_payload = {**result, "payouts": payouts}
            # note_path = "/mnt/data/market_sync_note.txt"
            # with open(note_path, "w") as f:
            #     json.dump(combined_payload, f, indent=2)
            # logger.info(f"Wrote combined payload to {note_path}")

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



if __name__ == "__main__":
    run_market_sync()

