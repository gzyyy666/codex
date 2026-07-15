from __future__ import annotations

import json
import copy
import importlib.util
import mimetypes
import os
import re
import sys
import threading
from datetime import datetime
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
from fitness_ledger_core.data_quality_view import SilentHealthCheck, acknowledge_issue, collect_issues  # noqa: E402
from fitness_ledger_core.analysis_export import build_export  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from cloud_sync.build_cloud_payload import main as build_cloud_replica, source_metadata  # noqa: E402
from cloud_sync.sync_to_cloud import sync_payload, validate_payload  # noqa: E402
from cloud_sync.upload_to_cloudbase import config_status, is_upload_configured, load_sync_config  # noqa: E402


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
        self.views = LedgerViewModels(data_file, dictionary_file)
        self.stable = load_stable_module()
        self.commands = LedgerCommandService(data_file, dictionary_file, backup_dir, self._parse_with_stable_app)
        self.data_check_state_file = Path(data_file).parent / "data_check_state.json"
        self.silent_health = SilentHealthCheck(
            Path(data_file), Path(dictionary_file), self.stable, self.data_check_state_file
        )
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
            "edit": True,
            "dictionary_admin": True,
            "custom_movement_canonicalization": True,
            "undo": True,
            "data_check_repair": True,
            "phase": "shared-platform-services",
        }

    def undo_status(self) -> dict:
        return self.commands.undo_status()

    def undo_last_write(self) -> dict:
        result = self.commands.undo_last_write()
        self.data._cache = None
        return result

    def data_check(self) -> dict:
        database, dictionary = self.commands.load_state()
        return collect_issues(database, dictionary, self.stable, self.data_check_state_file)

    def archive_health(self) -> dict:
        return self.silent_health.summary()

    def workout_reference(self, split: str) -> dict:
        return self.views.workout_reference(split)

    def movement_insight(self, name: str = "", movement_id: str = "", limit: int = 8) -> dict:
        return self.views.movement_history_by_id(movement_id, limit) if movement_id else self.views.movement_history(name, limit)

    def movement_history(self, movement_id: str = "", name: str = "", limit: int = 8, before_date: str = "") -> dict:
        if movement_id:
            return self.views.movement_history_by_id(movement_id, limit, before_date)
        return self.views.movement_history(name, limit)

    def analysis_export(self, request: dict) -> dict:
        return build_export(self.views, request)

    def acknowledge_data_issue(self, request: dict) -> dict:
        key = str(request.get("issue_key", "")).strip()
        if not key:
            raise LedgerCommandError("缺少问题标识。")
        return acknowledge_issue(self.data_check_state_file, key)

    @staticmethod
    def _cloud_sync_log(event: dict | None = None) -> list[dict]:
        log_path = PROJECT_DIR / "cloud_sync" / "out" / "sync_log.json"
        try:
            rows = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
        except (OSError, json.JSONDecodeError):
            rows = []
        if event:
            rows.insert(0, {"time": datetime.now().isoformat(timespec="seconds"), **event})
            rows = rows[:20]
            log_path.parent.mkdir(parents=True, exist_ok=True)
            temp = log_path.with_suffix(".tmp")
            temp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(log_path)
        return rows

    def cloud_sync_status(self) -> dict:
        out_dir = PROJECT_DIR / "cloud_sync" / "out"
        manifest_path = out_dir / "cloudbase_import" / "manifest.json"
        report_path = out_dir / "fitness_ledger_cloud_sync_report.json"
        state_path = out_dir / "sync_state.json"

        def read_json(path: Path):
            try:
                return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            except (OSError, json.JSONDecodeError):
                return None

        manifest = read_json(manifest_path)
        report = read_json(report_path)
        sync_state = read_json(state_path)
        try:
            tracker, dictionary = self.views.snapshot()
            current_source = source_metadata(tracker, dictionary)
        except (OSError, json.JSONDecodeError):
            current_source = {"source_fingerprint": "", "latest_record_date": ""}
        config = load_sync_config()
        upload_config = config_status(config)
        upload_ready = bool(upload_config.get("ready"))
        real_upload_ready = bool(upload_ready and upload_config.get("real_network_provider"))
        if real_upload_ready:
            sync_mode = "cloudbase_sdk_sync" if config.get("provider") in {"tencentcloud", "tcb", "sdk"} else "cloudbase_command_sync"
        elif upload_ready and config.get("provider") == "mock":
            sync_mode = "mock_sync"
        else:
            sync_mode = "manual_cloudbase_import"
        env_config = PROJECT_DIR / "mini_program" / "miniprogram" / "config" / "env.local.js"
        env_id = config.get("environment_id", "")
        if env_config.exists():
            match = re.search(r'envId\s*:\s*["\']([^"\']+)', env_config.read_text(encoding="utf-8"))
            env_id = env_id or (match.group(1) if match else "")
        # ``manifest`` describes the payload currently on disk; ``sync_state``
        # is written only after a verified SYNCED upload.  They must not be
        # collapsed into one status: a new local payload can exist after the
        # last verified upload.
        last_success = sync_state if (sync_state or {}).get("status") == "SYNCED" else {}
        last_attempt = report if report and report.get("status") != "DRY_RUN" else {}
        latest_result = last_attempt or last_success
        last_verification = last_success.get("cloud_verification") or {}
        current_payload_hash = (manifest or {}).get("payload_hash", "")
        last_success_hash = last_success.get("payload_hash", "")
        current_source_fingerprint = current_source["source_fingerprint"]
        payload_source_fingerprint = (manifest or {}).get("source_fingerprint", "")
        payload_stale = bool(
            manifest
            and (
                not payload_source_fingerprint
                or payload_source_fingerprint != current_source_fingerprint
            )
        )

        if manifest and payload_stale:
            current_sync_status = "LOCAL_NEWER"
        elif manifest and last_success:
            if current_payload_hash and last_success_hash and current_payload_hash != last_success_hash:
                current_sync_status = "LOCAL_NEWER"
            elif last_verification.get("verified"):
                current_sync_status = "SYNCED"
            else:
                current_sync_status = "CLOUD_MISMATCH"
        elif manifest and last_attempt:
            # A report from an attempted upload is a current outcome, except
            # DRY_RUN (excluded above), which only validates local files.
            current_sync_status = last_attempt.get("status", "READY")
        elif manifest:
            current_sync_status = "NOT_CONFIGURED" if not upload_ready else "READY"
        else:
            current_sync_status = latest_result.get("status", "NOT_CONFIGURED" if not upload_ready else "READY")
        return {
            "mode": sync_mode,
            "provider": config.get("provider", "disabled"),
            "upload_provider_ready": upload_ready,
            "network_upload_configured": real_upload_ready,
            "config_status": upload_config,
            "missing_config": upload_config.get("missing", []),
            "upload_verification_required": bool(upload_config.get("real_network_provider")),
            "auto_sync_enabled": bool(config.get("auto_sync_enabled")),
            "environment_configured": bool(env_id),
            "environment_id": env_id,
            "ledger_read_status": "unknown",
            "allowlist_status": "unknown",
            "raw_text_policy": (manifest or {}).get("raw_text_policy", "preview-disabled / excluded"),
            "local_latest_record_date": current_source["latest_record_date"],
            "cloud_latest_record_date": (
                last_verification.get("cloud_latest_record_date")
                or latest_result.get("cloud_latest_record_date", "")
            ),
            "sync_status": current_sync_status,
            "sync_version": (manifest or {}).get("sync_version", latest_result.get("sync_version", "")),
            "payload_hash": (manifest or {}).get("payload_hash", latest_result.get("payload_hash", "")),
            "payload_stale": payload_stale,
            "collection_hashes": (manifest or {}).get("collection_hashes", latest_result.get("collection_hashes", {})),
            "collection_status": latest_result.get("collection_results", {}),
            "last_sync_result": latest_result,
            "last_sync_status": last_success.get("status", ""),
            "last_sync_at": last_success.get("finished_at") or last_success.get("validated_at", ""),
            "last_cloud_verification": last_verification,
            "manifest": manifest,
            "validation": report,
            "logs": LedgerWebService._cloud_sync_log(),
            "import_directory": str(out_dir / "cloudbase_import"),
            "setup_guide": str(PROJECT_DIR / "mini_program" / "docs" / "CLOUDBASE_SETUP.md"),
        }

    @staticmethod
    def open_cloud_sync_target(target: str) -> dict:
        allowed = {
            "directory": PROJECT_DIR / "cloud_sync" / "out" / "cloudbase_import",
            "guide": PROJECT_DIR / "mini_program" / "docs" / "CLOUDBASE_SETUP.md",
        }
        path = allowed.get(str(target or ""))
        if path is None:
            raise LedgerCommandError("未知的云同步打开目标。")
        if target == "directory":
            path.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            raise LedgerCommandError(f"目标不存在：{path}")
        os.startfile(str(path))
        return {"opened": True, "target": target, "path": str(path)}

    def build_cloud_sync_package(self) -> dict:
        try:
            build_cloud_replica()
            report = validate_payload()
            LedgerWebService._cloud_sync_log({
                "trigger": "manual",
                "mode": "generate_payload",
                "result": "success",
                "latest_record_date": report.get("latest_record_date", ""),
                "error": "",
            })
        except Exception as exc:
            LedgerWebService._cloud_sync_log({
                "trigger": "manual", "mode": "generate_payload", "result": "error",
                "latest_record_date": "", "error": str(exc),
            })
            raise
        return {**self.cloud_sync_status(), "validation": report}

    def run_cloud_sync(self, request: dict) -> dict:
        try:
            build_cloud_replica()
            result = sync_payload(force=bool(request.get("force")))
            LedgerWebService._cloud_sync_log({
                "trigger": "manual",
                "mode": "sync_payload",
                "result": result.get("status", ""),
                "latest_record_date": result.get("latest_record_date", ""),
                "sync_version": result.get("sync_version", ""),
                "error": result.get("error", ""),
            })
        except Exception as exc:
            LedgerWebService._cloud_sync_log({
                "trigger": "manual", "mode": "sync_payload", "result": "error",
                "latest_record_date": "", "error": str(exc),
            })
            raise
        return {**self.cloud_sync_status(), "sync_result": result}

    def verify_cloud_sync(self, request: dict) -> dict:
        """Compare an exported CloudBase fl_meta row with the local manifest."""
        cloud_meta = request.get("cloud_meta") or {}
        if isinstance(cloud_meta, list):
            cloud_meta = cloud_meta[0] if cloud_meta else {}
        if not isinstance(cloud_meta, dict):
            raise LedgerCommandError("fl_meta 必须是 JSON 对象或单元素数组。")
        status = self.cloud_sync_status()
        manifest = status.get("manifest") or {}
        expected_counts = manifest.get("collections") or {}
        expected_hashes = manifest.get("collection_hashes") or {}
        actual_counts = cloud_meta.get("collection_counts") or {}
        actual_hashes = cloud_meta.get("collection_hashes") or {}
        checks = {
            "schema": cloud_meta.get("schema") == manifest.get("schema"),
            "generated_at": cloud_meta.get("generated_at") == manifest.get("generated_at"),
            "sync_version": cloud_meta.get("sync_version") == manifest.get("sync_version"),
            "payload_hash": cloud_meta.get("payload_hash") == manifest.get("payload_hash"),
            "collection_counts": all(
                int(actual_counts.get(name, -1)) == int(count)
                for name, count in expected_counts.items()
                if name != "fl_meta"
            ),
            "collection_hashes": all(
                str(actual_hashes.get(name, "")) == str(expected_hash)
                for name, expected_hash in expected_hashes.items()
                if name != "fl_meta"
            ),
        }
        collection_checks = {
            name: {
                "expected": int(count),
                "actual": int(actual_counts.get(name, -1)),
                "expected_hash": str(expected_hashes.get(name, "")),
                "actual_hash": str(actual_hashes.get(name, "")),
                "ok": (
                    int(actual_counts.get(name, -1)) == int(count)
                    and str(actual_hashes.get(name, "")) == str(expected_hashes.get(name, ""))
                ),
            }
            for name, count in expected_counts.items()
            if name != "fl_meta"
        }
        verified = bool(checks) and all(checks.values())
        LedgerWebService._cloud_sync_log({
            "trigger": "manual",
            "mode": "verify_cloud_replica",
            "result": "success" if verified else "mismatch",
            "latest_record_date": str(cloud_meta.get("latest_record_date", "")),
            "error": "" if verified else "Cloud metadata differs from the local payload.",
        })
        return {
            "verified": verified,
            "checks": checks,
            "collections": collection_checks,
            "expected_generated_at": manifest.get("generated_at", ""),
            "cloud_generated_at": cloud_meta.get("generated_at", ""),
            "local_latest_record_date": manifest.get("latest_record_date", ""),
            "cloud_latest_record_date": cloud_meta.get("latest_record_date", ""),
        }

    def dictionary_entries(self) -> list[dict]:
        return [
            {**item, "is_custom": self._is_custom_movement_id(item.get("movement_id", ""))}
            for item in self.commands.movement_definitions()
        ]

    def movement_groups(self) -> list[str]:
        return self.commands.movement_groups()

    @staticmethod
    def _is_custom_movement_id(movement_id: str) -> bool:
        """Mirror the Core identity gate without inferring from display text."""
        return bool(re.fullmatch(r"CUSTOM_\d+", str(movement_id or "").strip()))

    def canonical_movement_candidates(self, source_id: str = "", query: str = "") -> list[dict]:
        source_id = str(source_id or "").strip()
        rows = self.commands.movement_definitions()
        source = next((item for item in rows if str(item.get("movement_id", "")) == source_id), None)
        if not source or not self._is_custom_movement_id(source_id):
            raise LedgerCommandError("Source must be an existing CUSTOM movement.", "SOURCE_NOT_CUSTOM")
        needle = str(query or "").strip().casefold()
        candidates = []
        for item in rows:
            movement_id = str(item.get("movement_id", "")).strip()
            if (
                not movement_id
                or movement_id == source_id
                or self._is_custom_movement_id(movement_id)
                or item.get("active", True) is False
                or bool(item.get("deleted") or item.get("invalid") or item.get("temporary"))
                or not str(item.get("display_name", "")).strip()
            ):
                continue
            aliases = [str(value) for value in item.get("aliases", []) if str(value).strip()]
            searchable = " ".join([
                movement_id,
                str(item.get("display_name", "")),
                str(item.get("english_name", "")),
                *aliases,
            ]).casefold()
            if needle and needle not in searchable:
                continue
            candidates.append({
                "movement_id": movement_id,
                "display_name": str(item.get("display_name", "")),
                "english_name": str(item.get("english_name", "")),
                "aliases": aliases,
                "muscle_group": str(item.get("muscle_group", "Unclassified")),
                "history_count": int(item.get("history_count", 0) or 0),
            })
        return sorted(candidates, key=lambda item: (item["display_name"].casefold(), item["movement_id"]))

    def preview_custom_movement_merge(self, request: dict) -> dict:
        return self.commands.preview_merge_custom_movement(
            str(request.get("source_id", "")),
            str(request.get("target_id", "")),
        )

    def execute_custom_movement_merge(self, request: dict) -> dict:
        result = self.commands.merge_custom_movement(
            str(request.get("source_id", "")),
            str(request.get("target_id", "")),
            str(request.get("plan_identity", "")),
        )
        self.data._cache = None
        return result

    def promote_custom_movement(self, request: dict) -> dict:
        result = self.commands.promote_custom_movement(
            str(request.get("source_id", "")),
            request.get("definition") or {},
        )
        self.data._cache = None
        return result

    def create_dictionary_entry(self, request: dict) -> dict:
        result = self.commands.create_movement_definition(request)
        self.data._cache = None
        return result

    def update_dictionary_entry(self, request: dict) -> dict:
        movement_id = str(request.get("movement_id", "")).strip()
        if not movement_id:
            raise LedgerCommandError("Missing movement_id.")
        result = self.commands.update_movement_definition(movement_id, request.get("definition") or {})
        self.data._cache = None
        return result

    def set_dictionary_entry_active(self, request: dict) -> dict:
        movement_id = str(request.get("movement_id", "")).strip()
        if not movement_id or not isinstance(request.get("active"), bool):
            raise LedgerCommandError("movement_id and a boolean active state are required.")
        result = self.commands.set_movement_active(movement_id, request["active"])
        self.data._cache = None
        return result

    def delete_dictionary_entry(self, request: dict) -> dict:
        movement_id = str(request.get("movement_id", "")).strip()
        confirmation = str(request.get("confirmation", ""))
        if not movement_id:
            raise LedgerCommandError("Missing movement_id.")
        result = self.commands.delete_movement_definition(movement_id, confirmation)
        self.data._cache = None
        return result

    def update_record(self, request: dict) -> dict:
        result = self.commands.update_record(
            str(request.get("record_type", "")),
            str(request.get("record_id", "")),
            request.get("values") or {},
        )
        self.data._cache = None
        return result

    def update_movement_history(self, request: dict) -> dict:
        result = self.commands.update_movement_history(
            str(request.get("movement_id", "")),
            str(request.get("history_id", "")),
            request.get("values") or {},
        )
        self.data._cache = None
        return result

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
            for field in ("display_name", "notes", "_review_action", "_mapped_movement_id", "_muscle_group"):
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
        if name == "training":
            return self.views.training_archive(limit)
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
        dictionary_rows = self.commands.load_state()[1].get("movements", []) or []
        pinned_by_id = {str(item.get("movement_id", "")): bool(item.get("pinned", False)) for item in dictionary_rows}
        rank_by_id = {str(item.get("movement_id", "")): int(item.get("focus_rank", 0) or 0) for item in dictionary_rows}
        definitions = list(cache["movements_by_id"].values())
        if query.strip():
            definitions = self.data.find_movement_candidates(query, limit=limit)
        definitions = [item for item in definitions if item.active]
        if not query.strip():
            definitions.sort(
                key=lambda item: (
                    not pinned_by_id.get(str(item.movement_id), False),
                    rank_by_id.get(str(item.movement_id), 0),
                    item.display_name or item.english_name,
                )
            )
        return [
            {
                "movement_id": item.movement_id,
                "display_name": item.display_name,
                "english_name": item.english_name,
                "aliases": item.aliases,
                "muscle_group": item.muscle_group,
                "category": item.category,
                "active": item.active,
                "pinned": pinned_by_id.get(str(item.movement_id), False),
                "focus_rank": rank_by_id.get(str(item.movement_id), 0),
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
            elif parsed.path == "/api/undo-status":
                self.send_json(self.service.undo_status())
            elif parsed.path == "/api/data-check":
                self.send_json(self.service.data_check())
            elif parsed.path == "/api/archive-health":
                self.send_json(self.service.archive_health())
            elif parsed.path == "/api/cloud-sync/status":
                self.send_json(self.service.cloud_sync_status())
            elif parsed.path == "/api/workout-reference":
                self.send_json(self.service.workout_reference(query.get("split", [""])[0]))
            elif parsed.path == "/api/movement-insight":
                self.send_json(self.service.movement_insight(query.get("name", [""])[0], query.get("movement_id", [""])[0], int(query.get("limit", ["8"])[0])))
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
            elif parsed.path == "/api/dictionary":
                self.send_json(self.service.dictionary_entries())
            elif parsed.path == "/api/movement-groups":
                self.send_json(self.service.movement_groups())
            elif parsed.path == "/api/movements/canonical-candidates":
                self.send_json(self.service.canonical_movement_candidates(
                    query.get("source_id", [""])[0],
                    query.get("q", [""])[0],
                ))
            elif parsed.path == "/api/movement-history":
                movement = self.service.movement_history(
                    query.get("movement_id", [""])[0],
                    query.get("name", [""])[0],
                    int(query.get("limit", ["8"])[0]),
                    query.get("before_date", [""])[0],
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
            elif parsed.path == "/api/undo":
                self.send_json(self.service.undo_last_write())
            elif parsed.path == "/api/data-check/acknowledge":
                self.send_json(self.service.acknowledge_data_issue(request))
            elif parsed.path == "/api/cloud-sync/build":
                self.send_json(self.service.build_cloud_sync_package())
            elif parsed.path == "/api/cloud-sync/sync":
                self.send_json(self.service.run_cloud_sync(request))
            elif parsed.path == "/api/cloud-sync/verify":
                self.send_json(self.service.verify_cloud_sync(request))
            elif parsed.path == "/api/cloud-sync/open":
                self.send_json(self.service.open_cloud_sync_target(request.get("target", "")))
            elif parsed.path == "/api/analysis-export":
                self.send_json(self.service.analysis_export(request))
            elif parsed.path == "/api/save":
                self.send_json(self.service.save_review(request))
            elif parsed.path == "/api/dictionary/create":
                self.send_json(self.service.create_dictionary_entry(request))
            elif parsed.path == "/api/dictionary/update":
                self.send_json(self.service.update_dictionary_entry(request))
            elif parsed.path == "/api/dictionary/active":
                self.send_json(self.service.set_dictionary_entry_active(request))
            elif parsed.path == "/api/dictionary/delete":
                self.send_json(self.service.delete_dictionary_entry(request))
            elif parsed.path == "/api/movements/custom-merge/preview":
                self.send_json(self.service.preview_custom_movement_merge(request))
            elif parsed.path == "/api/movements/custom-merge/execute":
                self.send_json(self.service.execute_custom_movement_merge(request))
            elif parsed.path == "/api/movements/custom-promote":
                self.send_json(self.service.promote_custom_movement(request))
            elif parsed.path == "/api/record/update":
                self.send_json(self.service.update_record(request))
            elif parsed.path == "/api/movement-history/update":
                self.send_json(self.service.update_movement_history(request))
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
        except LedgerCommandError as exc:
            status = (
                HTTPStatus.INTERNAL_SERVER_ERROR
                if exc.code == "MIGRATION_FAILED"
                else HTTPStatus.CONFLICT
                if exc.code in {"PREVIEW_STALE", "MIGRATION_BLOCKED"}
                else HTTPStatus.BAD_REQUEST
            )
            self.send_json(
                {"error": str(exc), "code": exc.code, "details": exc.details},
                status,
            )
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
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
