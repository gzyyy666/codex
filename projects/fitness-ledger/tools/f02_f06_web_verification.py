"""Isolated HTTP verification for the F02/F06 Analysis Export boundary."""
from __future__ import annotations

import json
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fitness_ledger_core.formal_readonly_data_source import FormalReadOnlyDataSource
from web_desktop.backend.analysis_export_protocol import AnalysisExportProtocolService
from web_desktop.backend.server import LedgerWebService, create_server
from f02_f06_regression_test import _request, _state


def post(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def get(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.headers.get_content_type(), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get_content_type(), exc.read()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fl-f02-f06-web-") as temp:
        root = Path(temp)
        tracker, dictionary = _state()
        tracker_path = root / "tracker.json"
        dictionary_path = root / "movement_dictionary.json"
        tracker_path.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        dictionary_path.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
        protocol = AnalysisExportProtocolService(
            FormalReadOnlyDataSource(tracker_path, dictionary_path)
        )
        service = LedgerWebService(tracker_path, dictionary_path, root / "backups", analysis_export_protocol=protocol)
        server = create_server(port=0, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            page_status, page_type, page_body = get(base + "/")
            assert page_status == 200 and page_type == "text/html" and page_body
            health_status, health_type, _ = get(base + "/api/health")
            assert health_status == 200 and health_type == "application/json"

            resolve_status, resolved = post(
                base + "/api/analysis-export/v1/resolve",
                {"selector": {"kind": "movement_id", "value": "M1"}},
            )
            assert resolve_status == 200 and resolved["status"] == "resolved", resolved

            request = _request()
            preview_status, preview = post(
                base + "/api/analysis-export/v1/preview",
                {"request": request, "preview_context_id": "web-context-1"},
            )
            assert preview_status == 200 and preview["status"] == "preview_ready", preview
            assert preview["preview"]["record_count"] == 1

            update_status, update = post(
                base + "/api/record/update",
                {
                    "record_type": "body",
                    "record_id": "body-1",
                    "values": {"Weight (kg)": 72.3},
                    "expected_revision": 1,
                },
            )
            assert update_status == 200, update
            current = json.loads(tracker_path.read_text(encoding="utf-8"))
            assert current["daily_records"][0]["Weight (kg)"] == 72.3

            confirm_status, confirmed = post(
                base + "/api/analysis-export/v1/export",
                {
                    "request": request,
                    "confirmed": True,
                    "confirmation_token": preview["confirmation_token"],
                    "preview_context_id": "web-context-1",
                },
            )
            assert confirm_status == 200 and confirmed["status"] == "bundle_ready", confirmed
            artifact_status, artifact_type, artifact_body = get(
                base + "/api/analysis-export/v1/artifact/"
                + confirmed["artifact_id"]
                + "?format=json"
            )
            assert artifact_status == 200 and artifact_type == "application/json"
            assert json.loads(artifact_body)["records"][0]["weight_kg"] == 70.1

            new_preview_status, new_preview = post(
                base + "/api/analysis-export/v1/preview",
                {"request": request, "preview_context_id": "web-context-2"},
            )
            assert new_preview_status == 200 and new_preview["status"] == "preview_ready", new_preview
            assert new_preview["preview"]["record_count"] == 1
            new_token = new_preview["confirmation_token"]
            new_confirm_status, new_confirm = post(
                base + "/api/analysis-export/v1/export",
                {
                    "request": request,
                    "confirmed": True,
                    "confirmation_token": new_token,
                    "preview_context_id": "web-context-2",
                },
            )
            assert new_confirm_status == 200 and new_confirm["status"] == "bundle_ready", new_confirm
            new_artifact_status, _, new_artifact_body = get(
                base + "/api/analysis-export/v1/artifact/"
                + new_confirm["artifact_id"]
                + "?format=json"
            )
            assert new_artifact_status == 200
            assert json.loads(new_artifact_body)["records"][0]["weight_kg"] == 72.3

            invalid_status, invalid = post(
                base + "/api/analysis-export/v1/export",
                {"request": request, "confirmed": True, "confirmation_token": "invalid-token"},
            )
            assert invalid_status == 200 and invalid["status"] == "confirmation_mismatch", invalid

            dictionary_path.unlink()
            unavailable_status, unavailable = post(
                base + "/api/analysis-export/v1/preview",
                {"request": request, "preview_context_id": "web-unavailable"},
            )
            assert unavailable_status == 200 and unavailable["status"] == "formal_data_unavailable", unavailable

            print("WEB_VERIFICATION_OK")
            print("isolated_target=temporary tracker.json, movement_dictionary.json, backups")
            print("verified=GET page, health, resolver, preview, write-then-preview, confirm, artifact, invalid-token, unavailable-data")
            print("preview_before_write_weight=70.1")
            print("preview_after_write_weight=72.3")
            print("unavailable_http_status=200")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
