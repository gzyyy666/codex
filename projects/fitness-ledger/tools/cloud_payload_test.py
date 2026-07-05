from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
PAYLOAD = PROJECT / "cloud_sync" / "out" / "fitness_ledger_cloud_payload.json"
EXPECTED = {
    "fl_meta", "fl_latest_summary", "fl_daily_records", "fl_diet_records",
    "fl_training_sessions", "fl_movements", "fl_movement_history",
    "fl_search_index", "fl_raw_entries", "fl_data_quality_issues",
}


def main() -> None:
    subprocess.run([sys.executable, str(PROJECT / "cloud_sync" / "build_cloud_payload.py")], check=True)
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    assert set(payload) == EXPECTED
    meta = payload["fl_meta"][0]
    assert meta["schema"] == "fitness-ledger-read-replica-v2"
    assert meta["sync_state"] == "local_payload_only"
    assert meta["raw_text_policy"] == "preview-disabled"
    assert meta["collection_counts"] == {name: len(rows) for name, rows in payload.items() if name != "fl_meta"}
    assert all(not str(row.get("preview", "")) for row in payload["fl_raw_entries"])
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert '"raw record"' not in serialized
    assert '"raw"' not in serialized
    subprocess.run([sys.executable, str(PROJECT / "cloud_sync" / "sync_to_cloud.py"), "--dry-run"], check=True)
    report = json.loads(PAYLOAD.with_name("fitness_ledger_cloud_sync_report.json").read_text(encoding="utf-8"))
    assert report["network_request_made"] is False
    print("FITNESS_LEDGER_CLOUD_PAYLOAD_OK")


if __name__ == "__main__":
    main()
