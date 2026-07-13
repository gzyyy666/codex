from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from cloud_sync.build_cloud_payload import source_metadata
from web_desktop.backend import server
from web_desktop.backend.server import LedgerWebService


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def state(payload_hash: str) -> dict:
    return {
        "status": "SYNCED",
        "payload_hash": payload_hash,
        "finished_at": "2026-07-12T12:00:00",
        "cloud_verification": {"verified": True, "cloud_latest_record_date": "2026-07-12"},
    }


def main() -> None:
    original_project_dir = server.PROJECT_DIR
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-cloud-status-") as temp:
        root = Path(temp)
        tracker_file = root / "data" / "tracker.json"
        dictionary_file = root / "data" / "movement_dictionary.json"
        tracker = {"daily_records": [{"id": "body-1", "Date": "2026-07-12", "Weight (kg)": 70.0}]}
        dictionary = {"movements": []}
        write_json(tracker_file, tracker)
        write_json(dictionary_file, dictionary)
        service = LedgerWebService(tracker_file, dictionary_file, root / "data" / "backups")
        server.PROJECT_DIR = root
        try:
            manifest_path = root / "cloud_sync" / "out" / "cloudbase_import" / "manifest.json"
            state_path = root / "cloud_sync" / "out" / "sync_state.json"

            source = source_metadata(tracker, dictionary)
            write_json(manifest_path, {"payload_hash": "payload-a", **source})
            write_json(state_path, state("payload-a"))
            synced = service.cloud_sync_status()
            assert synced["sync_status"] == "SYNCED"
            assert synced["local_latest_record_date"] == "2026-07-12"
            assert synced["payload_stale"] is False

            tracker["daily_records"].append({"id": "body-2", "Date": "2026-07-13", "Weight (kg)": 69.8})
            write_json(tracker_file, tracker)
            before = (tracker_file.read_bytes(), manifest_path.read_bytes())
            new_date = service.cloud_sync_status()
            assert new_date["sync_status"] == "LOCAL_NEWER"
            assert new_date["local_latest_record_date"] == "2026-07-13"
            assert new_date["payload_stale"] is True
            assert before == (tracker_file.read_bytes(), manifest_path.read_bytes())

            tracker["daily_records"][-1]["Weight (kg)"] = 69.6
            write_json(tracker_file, tracker)
            same_date_change = service.cloud_sync_status()
            assert same_date_change["sync_status"] == "LOCAL_NEWER"
            assert same_date_change["local_latest_record_date"] == "2026-07-13"

            current_source = source_metadata(tracker, dictionary)
            write_json(manifest_path, {"payload_hash": "payload-b", **current_source})
            write_json(state_path, state("payload-a"))
            payload_not_uploaded = service.cloud_sync_status()
            assert payload_not_uploaded["sync_status"] == "LOCAL_NEWER"
            assert payload_not_uploaded["payload_stale"] is False

            write_json(state_path, state("payload-b"))
            uploaded = service.cloud_sync_status()
            assert uploaded["sync_status"] == "SYNCED"
            assert uploaded["last_sync_status"] == "SYNCED"

            state_path.unlink()
            write_json(root / "cloud_sync" / "out" / "fitness_ledger_cloud_sync_report.json", {"status": "DRY_RUN"})
            dry_run = service.cloud_sync_status()
            assert dry_run["sync_status"] != "SYNCED"

            write_json(state_path, state("payload-b"))
            write_json(manifest_path, {"payload_hash": "payload-b"})
            old_manifest = service.cloud_sync_status()
            assert old_manifest["sync_status"] == "LOCAL_NEWER"
            assert old_manifest["payload_stale"] is True
        finally:
            server.PROJECT_DIR = original_project_dir
    print("FITNESS_LEDGER_CLOUD_SYNC_STATUS_OK")


if __name__ == "__main__":
    main()
