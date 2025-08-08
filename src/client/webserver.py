from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/market-event":
            self.send_response(404); self.end_headers()
            self.wfile.write(b"Not Found"); return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400); self.end_headers()
            self.wfile.write(b"Invalid JSON"); return

        print("Webhook received:\n", json.dumps(payload, indent=2))

        self.send_response(200); self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, fmt, *args):  # silence default logging
        return

if __name__ == "__main__":
    host, port = "0.0.0.0", 8001
    print(f"Listening on http://{host}:{port}/market-event")
    HTTPServer((host, port), WebhookHandler).serve_forever()