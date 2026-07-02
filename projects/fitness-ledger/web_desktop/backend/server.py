from __future__ import annotations

import json
import copy
import importlib.util
import mimetypes
import sys
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.machinery import SourceFileLoader
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


PROJECT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
ASSET_DIR = PROJECT_DIR / "assets"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from mobile_viewer.data_access import LedgerDataAccess  # noqa: E402
from ledger_commands import DuplicateDateError, LedgerCommandError, LedgerCommandService  # noqa: E402


def load_stable_module():
    module_name = "fitness_ledger_stable_app"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    source = PROJECT_DIR / "stable_app.pyw"
    loader = SourceFileLoader(module_name, str(source))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise RuntimeError("Unable to load the shared Fitness Ledger parser.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


class LedgerWebService:
    """Local Web read model plus the shared review/save command boundary."""

    def __init__(
        self,
        data_file: Path | None = None,
        dictionary_file: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        data_file = data_file or PROJECT_DIR / "data" / "tracker.json"
        dictionary_file = dictionary_file or PROJECT_DIR / "data" / "movement_dictionary.json"
        backup_dir = backup_dir or PROJECT_DIR / "data" / "backups"
        self.data = LedgerDataAccess(data_file, dictionary_file)
        self.stable = load_stable_module()
        self.commands = LedgerCommandService(data_file, dictionary_file, backup_dir, self._parse_with_stable_app)
        self.pending_reviews: dict[str, dict] = {}
        self.pending_lock = threading.RLock()

    def _parse_with_stable_app(self, raw: str, database: dict, dictionary: dict) -> dict:
        parser = self.stable.FitnessTrackerApp.__new__(self.stable.FitnessTrackerApp)
        parser.database = database
        parser.movement_dictionary = dictionary
        parser.movement_definitions_by_id, parser.movement_definitions_by_alias = self.stable.movement_definition_index(
            dictionary
        )
        return parser.parse_entry(raw)

    def capabilities(self) -> dict:
        return {
            "read": True,
            "parse": True,
            "save": True,
            "edit": False,
            "undo": False,
            "phase": "shared-review-save",
        }

    def parse_entry(self, raw_text: str) -> dict:
        payload = self.commands.parse(raw_text)
        review_id = str(payload["review_id"])
        with self.pending_lock:
            self.pending_reviews[review_id] = copy.deepcopy(payload["review"])
        return payload

    def save_review(self, request: dict) -> dict:
        review_id = str(request.get("review_id", ""))
        submitted = request.get("review")
        if not review_id or not isinstance(submitted, dict):
            raise LedgerCommandError("Missing review data.")
        with self.pending_lock:
            original = self.pending_reviews.get(review_id)
        if original is None:
            raise LedgerCommandError("This review expired. Parse the entry again before saving.")
        if str(submitted.get("id", "")) != review_id or submitted.get("raw") != original.get("raw"):
            raise LedgerCommandError("The review identity or preserved raw input was changed.")
        reviewed = self._merge_allowed_review_edits(original, submitted)
        result = self.commands.save(reviewed, request.get("save_mode"))
        with self.pending_lock:
            self.pending_reviews.pop(review_id, None)
        self.data._cache = None
        return result

    @staticmethod
    def _merge_allowed_review_edits(original: dict, submitted: dict) -> dict:
        reviewed = copy.deepcopy(original)
        reviewed["date"] = submitted.get("date", reviewed.get("date"))
        allowed_sections = {
            "body": ("weight", "bowel_movement", "training_summary", "cardio_summary", "notes"),
            "diet": ("calories", "protein", "carbs", "fat", "food_summary", "notes"),
            "training": ("split", "standardized_summary", "notes"),
        }
        for section, fields in allowed_sections.items():
            source = submitted.get(section, {})
            target = reviewed.setdefault(section, {})
            if isinstance(source, dict):
                for field in fields:
                    if field in source:
                        target[field] = source[field]
        original_movements = reviewed.get("training", {}).get("movements", [])
        submitted_movements = submitted.get("training", {}).get("movements", [])
        if len(original_movements) != len(submitted_movements):
            raise LedgerCommandError("Movement rows cannot be added or removed during Web review.")
        for target, source in zip(original_movements, submitted_movements):
            if not isinstance(source, dict):
                raise LedgerCommandError("Invalid movement review data.")
            for field in ("display_name", "notes", "_review_action", "_mapped_movement_id"):
                if field in source:
                    target[field] = source[field]
        return reviewed

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
        definitions = [item for item in definitions if item.active]
        if not query.strip():
            definitions.sort(key=lambda item: item.display_name or item.english_name)
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

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 2_000_000:
            raise ValueError("Invalid request size.")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON object required.")
        return payload

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
                movement = self.service.data.get_movement_history(
                    query.get("name", [""])[0], int(query.get("limit", ["8"])[0])
                )
                if movement.get("movement") and not movement["movement"].get("active", True):
                    movement = {"query": query.get("name", [""])[0], "movement": None, "history": []}
                self.send_json(movement)
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
        parsed = urlparse(self.path)
        try:
            request = self.read_json_body()
            if parsed.path == "/api/parse":
                self.send_json(self.service.parse_entry(request.get("raw", "")))
            elif parsed.path == "/api/save":
                self.send_json(self.service.save_review(request))
            else:
                self.send_json({"error": "Unknown command."}, HTTPStatus.NOT_FOUND)
        except DuplicateDateError as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "code": "duplicate_date",
                    "duplicates": exc.duplicates,
                    "save_modes": ["overwrite", "append_training"],
                },
                HTTPStatus.CONFLICT,
            )
        except (LedgerCommandError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_json(
                {"error": "Shared command service failed.", "detail": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def create_server(
    host: str = "127.0.0.1",
    port: int = 8766,
    service: LedgerWebService | None = None,
) -> ThreadingHTTPServer:
    handler = type("ConfiguredLedgerRequestHandler", (LedgerRequestHandler,), {})
    handler.service = service or LedgerWebService()
    return ThreadingHTTPServer((host, port), handler)


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
