"""Local, no-data Preview server for Analysis Export Request v1."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "tools" / "analysis_export_request_preview"
EXAMPLES_ROOT = ROOT / "docs" / "experiments" / "evidence" / "analysis_export_request_examples"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_request import validate_json


class PreviewHandler(BaseHTTPRequestHandler):
    server_version = "FitnessLedgerRequestPreview/1"

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: object) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        route = urlparse(self.path).path
        if route == "/health":
            return self._json(200, {"status": "ok", "formal_data_read": False, "executor_called": False, "model_called": False})
        if route == "/api/examples":
            examples = []
            for path in sorted(EXAMPLES_ROOT.glob("*.json")):
                examples.append({"name": path.name, "request": json.loads(path.read_text(encoding="utf-8"))})
            return self._json(200, {"examples": examples})
        relative = "index.html" if route == "/" else route.lstrip("/")
        path = (STATIC_ROOT / relative).resolve()
        if STATIC_ROOT not in path.parents or not path.is_file():
            return self._send(404, "text/plain; charset=utf-8", b"Not found")
        content_types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
        return self._send(200, content_types.get(path.suffix, "application/octet-stream"), path.read_bytes())

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if urlparse(self.path).path != "/api/validate":
            return self._send(404, "text/plain; charset=utf-8", b"Not found")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length > 250_000:
            return self._json(413, {"error": "request too large"})
        body = self.rfile.read(length).decode("utf-8", errors="strict")
        result = validate_json(body)
        return self._json(200, result.to_dict())


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the no-data Analysis Export Request Preview")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), PreviewHandler)
    print(f"Analysis Export Request Preview: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
