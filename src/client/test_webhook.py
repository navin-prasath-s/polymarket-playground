from webhook_listener import WebhookListener

wl = WebhookListener(port=8001, path="/market-event")

def on_market_added(data: dict):
    print("[market_added]", len(data.get("markets", [])))

def on_market_resolved(data: dict):
    print("[market_resolved]", data)

def on_payout_logs(data: dict):
    print("[payout_logs]", len(data.get("payout_logs", [])))

wl.on("market_added", on_market_added)
wl.on("market_resolved", on_market_resolved)
wl.on("payout_logs", on_payout_logs)


wl.start()
input("Listening… press Enter to stop.\n")
wl.stop()