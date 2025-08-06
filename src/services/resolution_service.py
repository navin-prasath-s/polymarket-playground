import logging
from decimal import Decimal
from sqlalchemy.future import select
from sqlmodel import Session

from src.models.user_position import UserPosition
from src.models.user import User
from src.models.payout_log import PayoutLog

logger = logging.getLogger(__name__)


class ResolutionError(Exception):
    def __init__(self, stage: str, original: Exception):
        super().__init__(f"[{stage}] {original}")
        self.stage = stage
        self.original = original

# TODO: Covert to bulk operations where possible

class ResolutionService:
    @staticmethod
    def resolve_market_winners(
        db: Session,
        winning_markets: list[dict]
    ) -> list[dict]:
        """
        Orchestrate resolution of multiple markets: fetch data, process each position,
        and collect per-market summaries. Raises ResolutionError on any fatal error.
        """
        all_logs: list[dict] = []
        for wm in winning_markets:
            condition_id = wm.get("condition_id")
            try:
                logs  = ResolutionService._process_single_market(db, wm)
                all_logs.extend(logs)
            except Exception as e:
                logger.exception(f"Error resolving market {condition_id}")
                raise ResolutionError("resolve_market_winners", e)
        return all_logs


    @staticmethod
    def _process_single_market(
        db: Session,
        wm: dict
    ) -> list[dict]:
        """
        Handle the resolution of a single market: load data, process positions,
        and return the summary dictionary.
        """
        condition_id = wm["condition_id"]
        winning_tokens = set(wm.get("winning_token_ids", []))

        # Fetch required data
        positions = ResolutionService._fetch_positions(db, condition_id)
        user_profiles = ResolutionService._fetch_user_profiles(
            db, {pos.user_name for pos in positions}
        )

        payout_logs: list[dict] = []

        # Process each position
        for pos in positions:
            payout_log_obj  = ResolutionService._process_position(
                db, pos, user_profiles, winning_tokens
            )
            payout_logs.append(payout_log_obj.model_dump())

        return payout_logs

    @staticmethod
    def _fetch_positions(
        db: Session,
        condition_id: str
    ) -> list[UserPosition]:
        """Load all UserPosition rows for a given market."""
        stmt = select(UserPosition).where(UserPosition.market == condition_id)
        result = db.exec(stmt)
        return result.scalars().all()

    @staticmethod
    def _fetch_user_profiles(
        db: Session,
        names: set[str]
    ) -> dict[str, User]:
        """Load User profiles for a set of user IDs."""
        if not names:
            return {}
        stmt = select(User).where(User.name.in_(names))
        result = db.exec(stmt)
        return {u.name: u for u in result.scalars().all()}


    @staticmethod
    def _process_position(
        db: Session,
        pos: UserPosition,
        user: dict[str, User],
        winning_tokens: set[str]
    ) -> PayoutLog | None:
        """
        Process one position: stage a PayoutLog, update profile if winning,
        delete the position, and collect any errors. Returns a tuple:
        (payout_amount, payout_entry or None, list_of_error_strings).
        """

        is_winner = pos.token in winning_tokens

        # Stage log
        payout_log_obj  = PayoutLog(
                user_name=pos.user_name,
                market=pos.market,
                token=pos.token,
                shares_paid=(pos.shares if is_winner else Decimal("0")),
                is_winner=is_winner,
            )
        db.add(payout_log_obj)

        # Update balance if winner
        if is_winner:
            try:
                profile = user.get(pos.user_name)
                if profile:
                    profile.balance += pos.shares
            except Exception as e:
                logger.exception(f"Failed to update balance for user {pos.user_name}")


        # Delete position
        try:
            db.delete(pos)
        except Exception as e:
            logger.exception(
                f"Failed to delete UserPosition for user {pos.user_name} market {pos.market} token {pos.token}"
            )

        return payout_log_obj


