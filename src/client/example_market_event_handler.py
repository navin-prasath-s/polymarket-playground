from webhook_listener import WebhookListener, MarketEventHandler


class PrintHandler(MarketEventHandler):
    def on_market_added(self, data: dict) -> None:
        print("market_added:", data)

    def on_market_resolved(self, data: dict) -> None:
        print("market_resolved:", data)

    def on_payout_logs(self, data: dict) -> None:
        print("payout_logs:", data)


handler = PrintHandler()
wl = WebhookListener(port=8001, path="/market-event")
wl.set_handler(handler)

wl.start()
input("Listening\n")
wl.stop()