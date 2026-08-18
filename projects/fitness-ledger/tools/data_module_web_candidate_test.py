"""Local HTTP candidate preview for the Data Module contract."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.request
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402
from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore  # noqa: E402


REGISTRY_FILE = PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class DataModuleWebCandidateTests(unittest.TestCase):
    def test_candidate_http_preview_save_and_read_models(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fitness-ledger-web-data-module-") as temp:
            root = Path(temp)
            tracker = root / "tracker.json"
            dictionary = root / "movement_dictionary.json"
            definition_store = root / "data_module_definitions.json"
            write_json(tracker, {
                "daily_records": [{"Date": "2026-08-12", "Weight (kg)": 70}],
                "diet_records": [],
                "training_sessions": [],
                "movements": {},
                "raw_entries": [],
                "data_module_records": [],
            })
            write_json(dictionary, {"version": "1.0", "movements": []})
            DataModuleDefinitionStore.initialize(definition_store, REGISTRY_FILE, backup_dir=root / "definition-backups")
            service = LedgerWebService(
                tracker,
                dictionary,
                root / "backups",
                build_info_override={"branch": "candidate"},
                data_module_registry_file=definition_store,
            )
            server = create_server("127.0.0.1", 0, service)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"

                def get(path: str):
                    with urllib.request.urlopen(base + path, timeout=5) as response:
                        return response.status, json.loads(response.read().decode("utf-8"))

                def post(path: str, payload: dict):
                    request = urllib.request.Request(
                        base + path,
                        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=5) as response:
                        return response.status, json.loads(response.read().decode("utf-8"))

                with urllib.request.urlopen(base + "/data-module-candidate.html", timeout=5) as response:
                    page = response.read().decode("utf-8")
                    self.assertIn("Self-Service Data Module Candidate", page)
                    self.assertIn("Downstream Capability Evidence", page)
                status, capabilities = get("/api/capabilities")
                self.assertEqual(status, 200)
                self.assertTrue(capabilities["data_module_candidate"])
                _status, module_capabilities = get("/api/data-modules/capabilities")
                self.assertEqual({row["module_id"] for row in module_capabilities["modules"]}, {"waist_cm", "resting_hr"})
                _status, catalog = get("/api/data-modules/catalog")
                self.assertEqual({row["module_id"] for row in catalog["modules"]}, {"waist_cm", "resting_hr"})
                _status, product_catalog = get("/api/data-modules/product-catalog")
                self.assertEqual(
                    {row["value"] for row in product_catalog["placement_choices"]},
                    {"main", "detail", "history", "record"},
                )
                self.assertEqual(
                    {row["module_id"]: row["placement"] for row in product_catalog["modules"]},
                    {"waist_cm": "main", "resting_hr": "main"},
                )
                _status, preview = post("/api/data-modules/preview", {"raw": "2026-08-12 腰围 82.5 cm"})
                self.assertFalse(preview["write_attempted"])
                _status, saved = post("/api/data-modules/save", {"preview": preview, "confirmed": True})
                self.assertTrue(saved["changed"])
                _status, history = get("/api/data-modules/history?module_id=waist_cm")
                self.assertEqual(history["latest"]["value"], 82.5)
                _status, cloud = get("/api/data-modules/cloud-dry-run")
                self.assertFalse(cloud["meta"]["network_request_made"])
                _status, cloud_verified = post("/api/data-modules/cloud-verify", {"payload": cloud})
                self.assertTrue(cloud_verified["verified"])
                _status, cloud_roundtrip = post("/api/data-modules/cloud-roundtrip", {"payload": cloud})
                self.assertEqual(cloud_roundtrip["payload_hash"], cloud["meta"]["payload_hash"])
                _status, normal_export = get("/api/data-modules/export")
                self.assertEqual(len(normal_export["records"]), 1)
                _status, analysis_catalog = get("/api/data-modules/analysis-catalog")
                self.assertEqual([module["module_id"] for module in analysis_catalog["modules"]], ["waist_cm"])
                _status, mini = get("/api/data-modules/mini-contract")
                self.assertEqual(mini["modules"][0]["module_id"], "waist_cm")
                _status, template = get("/api/data-modules/llm-template")
                self.assertEqual(template["schema"], "fitness-ledger-llm-entry-template-v1")
                self.assertFalse(template["source"]["contains_personal_records"])
                _status, statistics = get("/api/data-modules/statistics?module_id=waist_cm")
                self.assertEqual(statistics["summary"]["count"], 1)
                _status, readiness = get("/api/data-modules/release-readiness")
                self.assertTrue(readiness["candidate_only"])
                self.assertFalse(readiness["production_mutation_allowed"])
                self.assertFalse(readiness["cloud"]["network_request_made"])
                self.assertFalse(readiness["mini"]["network_request_made"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
