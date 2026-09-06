"""Regression coverage for the formal export provider and adapter boundary."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.formal_readonly_data_source import FormalReadOnlyDataSource
from ledger_commands import LedgerCommandService
from web_desktop.backend.analysis_export_protocol import AnalysisExportProtocolService


def _state(*, instance_excluded: bool = False, movement_excluded: bool = False):
    history = {
        "id": "history-1",
        "movement_id": "M1",
        "date": "2099-12-24",
        "sets": [{"weight": 60, "reps": 8, "sets": 3}],
        "notes": "instance note",
        "exclude_from_progress": instance_excluded,
        "training_session_id": "session-1",
    }
    tracker = {
        "daily_records": [
            {"id": "body-1", "Date": "2099-12-24", "Weight (kg)": 70.1,
             "Cardio": "daily cardio", "Notes": "body note", "revision": 1}
        ],
        "diet_records": [],
        "training_sessions": [{
            "id": "session-1", "Date": "2099-12-24",
            "Standardized Summary": "independent summary",
            "movement_items": [copy.deepcopy(history)], "revision": 1,
        }],
        "movements": {"M1": {"movement_id": "M1", "name": "卧推", "history": [history]}},
        "raw_entries": [],
    }
    dictionary = {"version": "test-1", "movements": [{
        "movement_id": "M1", "display_name": "卧推", "muscle_group": "Chest",
        "aliases": ["bench"], "active": True,
        "exclude_from_progress": movement_excluded,
    }]}
    return tracker, dictionary


def _request():
    return {
        "request_version": "1.1", "purpose": "regression",
        "datasets": [{"dataset_id": "body_check", "type": "body",
                       "time_range": {"mode": "all_available"}, "filters": {},
                       "fields": ["date", "weight_kg"]}],
        "raw": False, "output": {"formats": ["json"]},
    }


class F02F06RegressionTest(unittest.TestCase):
    def _files(self, *, instance_excluded=False, movement_excluded=False):
        temp = tempfile.TemporaryDirectory(prefix="fl-f02-f06-")
        root = Path(temp.name)
        tracker, dictionary = _state(instance_excluded=instance_excluded,
                                      movement_excluded=movement_excluded)
        tracker_path, dictionary_path = root / "tracker.json", root / "movement_dictionary.json"
        tracker_path.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        dictionary_path.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
        return temp, root, tracker_path, dictionary_path

    def test_f02_new_preview_refreshes_and_confirmation_uses_preview_snapshot(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        commands = LedgerCommandService(tracker_path, dictionary_path, root / "backups", lambda *_: {})
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        commands.update_record("body", "body-1", {"Weight (kg)": 71.2}, expected_revision=1)
        preview = protocol.preview({"request": _request()})
        self.assertEqual(preview["status"], "preview_ready")
        self.assertEqual(preview["preview"]["record_count"], 1)
        commands.update_record("body", "body-1", {"Weight (kg)": 72.3}, expected_revision=2)
        exported = protocol.export({"request": _request(), "confirmed": True,
                                    "confirmation_token": preview["confirmation_token"]})
        self.assertEqual(exported["status"], "bundle_ready")
        _, payload = protocol.artifact(exported["artifact_id"], "json")
        self.assertEqual(json.loads(payload)["records"][0]["weight_kg"], 71.2)
        current = json.loads(tracker_path.read_text(encoding="utf-8"))
        self.assertEqual(current["daily_records"][0]["Weight (kg)"], 72.3)

    def test_f02_export_does_not_modify_formal_files(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        before = (tracker_path.read_bytes(), dictionary_path.read_bytes())
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        preview = protocol.preview({"request": _request()})
        result = protocol.export({"request": _request(), "confirmed": True,
                                  "confirmation_token": preview["confirmation_token"]})
        self.assertEqual(result["status"], "bundle_ready")
        self.assertEqual((tracker_path.read_bytes(), dictionary_path.read_bytes()), before)

    def test_f06_instance_exclusion_is_preserved_and_history_remains(self):
        temp, root, tracker_path, dictionary_path = self._files(instance_excluded=True)
        self.addCleanup(temp.cleanup)
        provider = FormalReadOnlyDataSource(tracker_path, dictionary_path)
        request = {"request_version": "1.1", "purpose": "regression", "datasets": [{
            "dataset_id": "movement_check", "type": "movement_progress",
            "time_range": {"mode": "all_available"},
            "filters": {"movement_selector": {"kind": "movement_id", "value": "M1"}},
            "fields": ["date", "movement_id", "sets"], "notes_scope": "movement",
        }], "raw": False, "output": {"formats": ["json"]}}
        bundle = provider.materialize(request)
        self.assertEqual(bundle["records"], [])
        self.assertEqual(bundle["quality_profile"]["progress_exclusions"]["excluded_record_count"], 1)
        saved = json.loads(tracker_path.read_text(encoding="utf-8"))
        self.assertTrue(saved["training_sessions"][0]["movement_items"][0]["exclude_from_progress"])

    def test_f06_movement_exclusion_is_preserved(self):
        temp, root, tracker_path, dictionary_path = self._files(movement_excluded=True)
        self.addCleanup(temp.cleanup)
        provider = FormalReadOnlyDataSource(tracker_path, dictionary_path)
        request = {"request_version": "1.1", "purpose": "regression", "datasets": [{
            "dataset_id": "movement_check", "type": "movement_progress",
            "time_range": {"mode": "all_available"},
            "filters": {"movement_selector": {"kind": "movement_id", "value": "M1"}},
            "fields": ["date", "movement_id", "sets"],
        }], "raw": False, "output": {"formats": ["json"]}}
        bundle = provider.materialize(request)
        self.assertEqual(bundle["records"], [])
        self.assertEqual(bundle["quality_profile"]["progress_exclusions"]["excluded_movement_count"], 1)


if __name__ == "__main__":
    unittest.main()
