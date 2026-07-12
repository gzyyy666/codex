from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from cloud_sync.build_cloud_payload import main as build_cloud_payload
from cloud_sync.upload_to_cloudbase import DRY_RUN, NO_CHANGES, NOT_CONFIGURED, upload_payload

OUT_DIR = PROJECT_DIR / "cloud_sync" / "out"
PAYLOAD_PATH = OUT_DIR / "fitness_ledger_cloud_payload.json"
REPORT_PATH = OUT_DIR / "fitness_ledger_cloud_sync_report.json"
STATE_PATH = OUT_DIR / "sync_state.json"

EXPECTED = {
    "fl_meta", "fl_latest_summary", "fl_daily_records", "fl_diet_records",
    "fl_training_sessions", "fl_movements", "fl_movement_history",
    "fl_raw_entries", "fl_search_index", "fl_data_quality_issues",
}


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_report(report: dict) -> dict:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _manifest() -> dict:
    path = OUT_DIR / "cloudbase_import" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Build the payload first with build_cloud_payload.py.")
    return _read_json(path)


def validate_payload() -> dict:
    """Validate the generated replica package without making a network request."""
    if not PAYLOAD_PATH.exists():
        raise FileNotFoundError("Build the payload first with build_cloud_payload.py.")
    payload = _read_json(PAYLOAD_PATH)
    missing = sorted(EXPECTED.difference(payload))
    invalid = sorted(name for name, rows in payload.items() if not isinstance(rows, list))
    if missing or invalid:
        raise ValueError(f"Invalid cloud payload; missing={missing}, non_list={invalid}")

    meta = payload["fl_meta"][0] if payload.get("fl_meta") else {}
    report = {
        "status": DRY_RUN,
        "network_request_made": False,
        "validated_at": _now(),
        "payload": str(PAYLOAD_PATH),
        "sync_version": meta.get("sync_version", ""),
        "payload_hash": meta.get("payload_hash", ""),
        "latest_record_date": meta.get("latest_record_date", ""),
        "collection_hashes": meta.get("collection_hashes", {}),
        "collections": {name: len(rows) for name, rows in payload.items()},
        "warnings": ["未执行 CloudBase 网络上传；请同步或手动导入后再核对 fl_meta。"],
    }
    return _write_report(report)


def sync_payload(force: bool = False, config_path: str | Path | None = None) -> dict:
    """Upload the prepared import files through the configured provider."""
    manifest = _manifest()
    last_state = _read_json(STATE_PATH) if STATE_PATH.exists() else {}
    same_payload = last_state.get("payload_hash") == manifest.get("payload_hash")
    if not force and last_state.get("status") == "SYNCED" and same_payload:
        report = {
            "status": NO_CHANGES,
            "network_request_made": False,
            "validated_at": _now(),
            "sync_version": manifest.get("sync_version", ""),
            "payload_hash": manifest.get("payload_hash", ""),
            "latest_record_date": manifest.get("latest_record_date", ""),
            "collections": manifest.get("collections", {}),
            "collection_hashes": manifest.get("collection_hashes", {}),
            "last_sync": last_state,
            "warnings": [],
        }
        return _write_report(report)

    result = upload_payload(config_path)
    report = {
        **result,
        "network_request_made": result.get("status") != NOT_CONFIGURED,
        "validated_at": _now(),
        "collections": manifest.get("collections", {}),
        "collection_hashes": manifest.get("collection_hashes", {}),
    }
    _write_report(report)
    if result.get("status") == "SYNCED":
        STATE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or sync the Fitness Ledger CloudBase payload.")
    parser.add_argument("--dry-run", action="store_true", help="Validate local payload without network upload.")
    parser.add_argument("--sync", action="store_true", help="Build payload, upload with configured provider, and verify.")
    parser.add_argument("--force", action="store_true", help="Upload even when payload_hash is unchanged.")
    parser.add_argument("--config", default="", help="Optional local sync config JSON path.")
    args = parser.parse_args()

    if args.sync:
        build_cloud_payload()
        report = sync_payload(force=args.force, config_path=args.config or None)
        print(f"{report['status']}: {report.get('sync_version', '')}")
        print(f"report: {REPORT_PATH}")
        return

    if not args.dry_run:
        raise SystemExit("Use --dry-run or --sync.")
    report = validate_payload()
    print("DRY RUN: no network request was made.")
    for name, count in report["collections"].items():
        print(f"{name}: {count}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
