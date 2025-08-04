import logging
import os

import httpx
from dotenv import load_dotenv


load_dotenv()

subscriber_url = os.getenv("SUBSCRIBER_URL", "http://localhost:8001/market-event")

logger = logging.getLogger(__name__)



def emit_market_event(event_type: str, data: dict):
    payload = {"event": event_type, "data": data}
    try:
        resp = httpx.post(subscriber_url, json=payload, timeout=2)
        resp.raise_for_status()
        logger.info(f"Emitted {event_type} to {subscriber_url}")
    except Exception as e:
        logger.warning(f"Failed to emit {event_type} to {subscriber_url}: {e}")
