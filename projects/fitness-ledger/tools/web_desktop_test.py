from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from web_desktop.backend.server import create_server


def fetch(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status, response.headers.get_content_type(), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get_content_type(), exc.read()


def main() -> None:
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for endpoint in ("/api/health", "/api/capabilities", "/api/today", "/api/recent", "/api/body", "/api/diet", "/api/training", "/api/movements"):
            status, content_type, body = fetch(base + endpoint)
            assert status == 200, (endpoint, status)
            assert content_type == "application/json", (endpoint, content_type)
            json.loads(body.decode("utf-8"))

        status, content_type, body = fetch(base + "/")
        assert status == 200
        assert content_type == "text/html"
        assert b"Fitness Ledger Web" in body

        request = urllib.request.Request(base + "/api/parse", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(request, timeout=3)
            raise AssertionError("Write boundary unexpectedly accepted POST")
        except urllib.error.HTTPError as exc:
            assert exc.code == 501
    finally:
        server.shutdown()
        server.server_close()
    print("FITNESS_LEDGER_WEB_FOUNDATION_OK")


if __name__ == "__main__":
    main()
