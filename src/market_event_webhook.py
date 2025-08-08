import logging
import os
from decimal import Decimal
from enum import Enum

import httpx
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv


load_dotenv()

subscriber_url = os.getenv("SUBSCRIBER_URL", "http://localhost:8001/market-event")

logger = logging.getLogger(__name__)

class MarketEventType(Enum):
    MARKET_ADDED = "market_added"   # JSON payload list of {"condition_id": str, "question": str, "description": str, "tokens": list[str]}
    MARKET_RESOLVED = "market_resolved"   # JSON payload list of {"condition_id": str, "winning_token": str}
    PAYOUT_LOGS = "payout_logs"  # JSON payload list of {"user_name": str, "market": str, "token": str, "shares_paid": Decimal, "is_winner": bool, "timestamp": datetime}




def emit_market_event(event_type: str, data: dict):
    payload = {"event": event_type, "data": data}
    json_payload = jsonable_encoder(
        payload,
        custom_encoder={
            Decimal: lambda v: str(v),  # money-safe string
        },
    )
    try:
        resp = httpx.post(subscriber_url, json=json_payload, timeout=2)
        resp.raise_for_status()
        logger.info(f"Emitted {event_type} to {subscriber_url}")
    except Exception as e:
        logger.warning(f"Failed to emit {event_type} to {subscriber_url}: {e}")


