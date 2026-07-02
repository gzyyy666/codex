from __future__ import annotations

import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


PROJECT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
ASSET_DIR = PROJECT_DIR / "assets"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from mobile_viewer.data_access import LedgerDataAccess  # noqa: E402


class LedgerWebService:
    """Read-only application service for the first web migration phase."""

    def __init__(self) -> None:
        self.data = LedgerDataAccess()

    def capabilities(self) -> dict:
        return {
            "read": True,
            "parse": False,
            "save": False,
            "edit": False,
            "undo": False,
            "phase": "foundation-read-only",
        }

    def recent(self, limit: int = 3) -> list[dict]:
        results = []
        for entry_date in self.data.all_dates()[: max(1, min(limit, 20))]:
            detail = self.data.get_record_detail(entry_date)
            body = detail.get("body", {})
            diet = detail.get("diet", {})
            training = detail.get("training", [])
            results.append(
                {
                    "date": entry_date,
                    "weight": body.get("Weight (kg)", ""),
                    "bowel": body.get("Bowel Movement", ""),
                    "cardio": body.get("Cardio", ""),
                    "split": ", ".join(str(item.get("split", "")) for item in training if item.get("split")),
                    "calories": diet.get("Calories (kcal)", ""),
                    "protein": diet.get("Protein (g)", ""),
                    "carbs": diet.get("Carbs (g)", ""),
                    "fat": diet.get("Fat (g)", ""),
                }
            )
        return results

    def collection(self, name: str, limit: int = 50) -> list[dict]:
        tracker = self.data._tracker()
        mapping = {
            "body": "daily_records",
            "diet": "diet_records",
            "training": "training_sessions",
        }
        key = mapping[name]
        date_key = "Date"
        rows = sorted(tracker.get(key, []), key=lambda row: str(row.get(date_key, "")), reverse=True)
        return rows[: max(1, min(limit, 200))]

    def movement_index(self, query: str = "", limit: int = 80) -> list[dict]:
        cache = self.data._ensure_loaded()
        definitions = list(cache["movements_by_id"].values())
        if query.strip():
            definitions = self.data.find_movement_candidates(query, limit=limit)
        else:
            definitions.sort(key=lambda item: (not item.active, item.display_name or item.english_name))
        return [
            {
                "movement_id": item.movement_id,
                "display_name": item.display_name,
                "english_name": item.english_name,
                "aliases": item.aliases,
                "muscle_group": item.muscle_group,
                "category": item.category,
                "active": item.active,
            }
            for item in definitions[: max(1, min(limit, 200))]
        ]


class LedgerRequestHandler(BaseHTTPRequestHandler):
    service = LedgerWebService()

    def log_message(self, _format: str, *_args) -> None:
        return

    def send_json(self, payload, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                self.send_json({"ok": True, "service": "fitness-ledger-web"})
            elif parsed.path == "/api/capabilities":
                self.send_json(self.service.capabilities())
            elif parsed.path == "/api/today":
                self.send_json(self.service.data.get_today_summary())
            elif parsed.path == "/api/recent":
                self.send_json(self.service.recent(int(query.get("limit", ["3"])[0])))
            elif parsed.path == "/api/body":
                self.send_json(self.service.collection("body", int(query.get("limit", ["50"])[0])))
            elif parsed.path == "/api/diet":
                self.send_json(self.service.collection("diet", int(query.get("limit", ["50"])[0])))
            elif parsed.path == "/api/training":
                self.send_json(self.service.collection("training", int(query.get("limit", ["50"])[0])))
            elif parsed.path == "/api/movements":
                self.send_json(self.service.movement_index(query.get("q", [""])[0], int(query.get("limit", ["80"])[0])))
            elif parsed.path == "/api/movement-history":
                self.send_json(
                    self.service.data.get_movement_history(
                        query.get("name", [""])[0], int(query.get("limit", ["8"])[0])
                    )
                )
            elif parsed.path == "/api/record":
                self.send_json(self.service.data.get_record_detail(query.get("date", [""])[0]))
            elif parsed.path == "/api/search":
                self.send_json(self.service.data.search_records(query.get("q", [""])[0], query.get("scope", ["30d"])[0]))
            elif parsed.path.startswith("/app-assets/"):
                relative = Path(unquote(parsed.path.removeprefix("/app-assets/"))).name
                self.send_file(ASSET_DIR / relative)
            else:
                relative = parsed.path.lstrip("/") or "index.html"
                candidate = (FRONTEND_DIR / unquote(relative)).resolve()
                if FRONTEND_DIR.resolve() not in candidate.parents and candidate != FRONTEND_DIR.resolve():
                    self.send_error(HTTPStatus.FORBIDDEN)
                else:
                    self.send_file(candidate)
        except (ValueError, TypeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json({"error": "Local data service failed", "detail": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:  # noqa: N802
        self.send_json(
            {
                "error": "Write bridge is intentionally disabled in the foundation phase.",
                "next": "Route commands through the existing backup and atomic-save workflow before enabling writes.",
            },
            HTTPStatus.NOT_IMPLEMENTED,
        )


def create_server(host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), LedgerRequestHandler)


def main() -> None:
    server = create_server()
    print("Fitness Ledger Web: http://127.0.0.1:8766")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
