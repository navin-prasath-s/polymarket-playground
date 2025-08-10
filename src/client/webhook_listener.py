import json
import threading
from typing import Callable, Dict, List, Optional
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from abc import ABC, abstractmethod

Handler = Callable[[dict], None]



class EventBus:
    def __init__(self):
        self._subs: Dict[str, List[Handler]] = {}

    def on(self, event: str, handler: Handler):
        self._subs.setdefault(event, []).append(handler)

    def emit(self, event: str, data: dict):
        for h in self._subs.get(event, []):
            try:
                h(data)
            except Exception as e:
                print(f"[handler error] {event}: {e}")


class _Handler(BaseHTTPRequestHandler):
    path_allowed = "/market-event"
    bus: EventBus

    def do_POST(self):
        if self.path != self.path_allowed:
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            event = payload.get("event")
            data = payload.get("data") or {}
            if not event:
                raise ValueError("Missing 'event'")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Bad payload: {e}".encode())
            return

        # Dispatch
        self.bus.emit(event, data)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *_a, **_k):  # silence default logging
        return


def _make_handler(bus: EventBus, path: str):
    return type("BoundHandler", (_Handler,), {"bus": bus, "path_allowed": path})


class WebhookListener:
    def __init__(self, *, host="0.0.0.0", port=8001, path="/market-event"):
        self.host, self.port, self.path = host, port, path
        self.bus = EventBus()
        self._server = None
        self._thread = None
        self._handler_instance: Optional[MarketEventHandler] = None

    def set_handler(self, handler: 'MarketEventHandler'):
        """Set the handler instance that will process market events"""
        self._handler_instance = handler
        # Register all the handler methods
        self.bus.on("market_added", handler.on_market_added)
        self.bus.on("market_resolved", handler.on_market_resolved)
        self.bus.on("payout_logs", handler.on_payout_logs)

    def on(self, event: str, handler: Handler):
        """Direct function registration (alternative to class-based handlers)"""
        self.bus.on(event, handler)

    def start(self):
        Handler = _make_handler(self.bus, self.path)
        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        print(f"Listening on http://{self.host}:{self.port}{self.path}")

    def stop(self):
        if not self._server: return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


class MarketEventHandler(ABC):
    """
    Abstract base class for handling market events.

    Users should inherit from this class and implement the methods
    to handle events according to their needs (database operations,
    logging, notifications, etc.)
    """

    @abstractmethod
    def on_market_added(self, data: dict) -> None:
        """
        Called when new markets are added.

        Args:
            data: Dictionary containing market data as a list

        Expected data structure:
        [
            {
                "condition_id": "abc123",
                "question": "Will it rain tomorrow?",
                "description": "Resolves YES if...",
                "tokens": ["YES", "NO"]
            },
            ...
        ]
        """
        pass

    @abstractmethod
    def on_market_resolved(self, data: dict) -> None:
        """
        Called when markets are resolved.

        Args:
            data: Dictionary containing resolution data as a list

        Expected data structure:
        [
            {
                "condition_id": "abc123",
                "winning_token": "YES"
            },
            ...
        ]
        """
        pass

    @abstractmethod
    def on_payout_logs(self, data: dict) -> None:
        """
        Called when payout logs are received.

        Args:
            data: Dictionary containing payout information as a list

        Expected data structure:
        [
            {
                "user_name": "alice",
                "market": "Will it rain tomorrow?",
                "token": "YES",
                "shares_paid": Decimal("100.50"),
                "is_winner": True,
                "timestamp": datetime(2024, 1, 1, 12, 0, 0)
            },
            ...
        ]
        """
        pass