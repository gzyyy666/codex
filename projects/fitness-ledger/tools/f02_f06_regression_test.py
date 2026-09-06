"""Regression coverage for the formal export provider and adapter boundary."""
from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.formal_readonly_data_source import FormalReadOnlyDataSource
from fitness_ledger_core.formal_readonly_data_source import FormalReadOnlyDataSourceError
from ledger_commands import LedgerCommandService
from web_desktop.backend.analysis_export_protocol import AnalysisExportProtocolService
from web_desktop.backend.server import LedgerWebService


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

    def test_canonical_history_is_exported_without_legacy_projection(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
        tracker["movements"] = {}
        tracker_path.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        request = {"request_version": "1.1", "purpose": "regression", "datasets": [{
            "dataset_id": "movement_check", "type": "movement_progress",
            "time_range": {"mode": "all_available"},
            "filters": {"movement_selector": {"kind": "movement_id", "value": "M1"}},
            "fields": ["date", "movement_id", "sets"],
        }], "raw": False, "output": {"formats": ["json"]}}
        bundle = FormalReadOnlyDataSource(tracker_path, dictionary_path).materialize(request)
        self.assertEqual(len(bundle["records"]), 1)
        self.assertEqual(bundle["records"][0]["movement_id"], "M1")

    def test_latest_n_counts_non_excluded_sessions(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
        sessions = []
        for offset in range(8):
            date = f"2099-12-{24 - offset:02d}"
            excluded = offset < 2
            history = {"id": f"history-{offset}", "movement_id": "M1", "date": date,
                       "sets": [{"weight": 60 + offset, "reps": 8, "sets": 3}],
                       "exclude_from_progress": excluded}
            sessions.append({"id": f"session-{offset}", "Date": date,
                             "movement_items": [history]})
        tracker["training_sessions"] = sessions
        tracker["movements"] = {}
        tracker_path.write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        request = {"request_version": "1.1", "purpose": "regression", "datasets": [{
            "dataset_id": "movement_check", "type": "movement_progress",
            "time_range": {"mode": "latest_matching_sessions", "sessions": 6},
            "filters": {"movement_selector": {"kind": "movement_id", "value": "M1"}},
            "fields": ["date", "movement_id", "sets"],
        }], "raw": False, "output": {"formats": ["json"]}}
        bundle = FormalReadOnlyDataSource(tracker_path, dictionary_path).materialize(request)
        self.assertEqual(len(bundle["records"]), 6)
        self.assertEqual({row["date"] for row in bundle["records"]},
                         {f"2099-12-{day:02d}" for day in range(17, 23)})

    def test_resolver_refreshes_dictionary_without_preview(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
        dictionary["movements"][0]["display_name"] = "新卧推"
        dictionary_path.write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
        result = protocol.resolve({"selector": {"kind": "movement_name", "value": "新卧推"}})
        self.assertEqual(result["status"], "resolved")

    def test_unstable_formal_reads_are_protocol_failures(self):
        for missing_name in ("tracker", "dictionary"):
            temp, root, tracker_path, dictionary_path = self._files()
            self.addCleanup(temp.cleanup)
            protocol = AnalysisExportProtocolService(
                FormalReadOnlyDataSource(tracker_path, dictionary_path)
            )
            (tracker_path if missing_name == "tracker" else dictionary_path).unlink()
            result = protocol.preview({"request": _request()})
            self.assertEqual(result["status"], "formal_data_unavailable")
            self.assertEqual(
                result["errors"][0]["code"], "FORMAL_SNAPSHOT_UNAVAILABLE"
            )

    def test_incomplete_formal_json_is_protocol_failure(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        dictionary_path.write_text("{", encoding="utf-8")
        result = protocol.resolve({"selector": {"kind": "movement_id", "value": "M1"}})
        self.assertEqual(result["status"], "formal_data_unavailable")
        self.assertEqual(result["errors"][0]["code"], "FORMAL_SNAPSHOT_UNAVAILABLE")

    def test_provider_refresh_failure_is_protocol_failure(self):
        class FailingProvider:
            source_kind = "formal_local_json_read_only"
            formal_data_available = True

            def refresh(self):
                raise FormalReadOnlyDataSourceError("injected snapshot failure")

        protocol = AnalysisExportProtocolService(FailingProvider())
        result = protocol.preview({"request": _request()})
        self.assertEqual(result["status"], "formal_data_unavailable")
        self.assertEqual(result["errors"][0]["code"], "FORMAL_SNAPSHOT_UNAVAILABLE")

    def test_web_service_fails_closed_when_formal_json_is_incomplete(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        dictionary_path.write_text("{", encoding="utf-8")
        service = LedgerWebService(tracker_path, dictionary_path, root / "backups")
        self.assertEqual(
            service.analysis_export_protocol.provider.availability_status,
            "snapshot_unavailable",
        )

    def test_preview_memory_expires_and_duplicate_confirm_is_rejected(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        protocol.PREVIEW_TTL_SECONDS = 0
        preview = protocol.preview({"request": _request()})
        result = protocol.export({"request": _request(), "confirmed": True,
                                  "confirmation_token": preview["confirmation_token"]})
        self.assertEqual(result["status"], "confirmation_mismatch")
        protocol.PREVIEW_TTL_SECONDS = 900
        preview = protocol.preview({"request": _request()})
        confirmed = protocol.export({"request": _request(), "confirmed": True,
                                     "confirmation_token": preview["confirmation_token"]})
        self.assertEqual(confirmed["status"], "bundle_ready")
        duplicate = protocol.export({"request": _request(), "confirmed": True,
                                     "confirmation_token": preview["confirmation_token"]})
        self.assertEqual(duplicate["status"], "confirmation_mismatch")

    def test_preview_and_artifact_counts_are_bounded(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        protocol.MAX_PREVIEWS = 2
        for index in range(5):
            protocol.preview({"request": _request(), "preview_context_id": str(index)})
        protocol._prune_memory()
        self.assertLessEqual(len(protocol._previews), 2)
        protocol.MAX_ARTIFACTS = 2
        for _index in range(5):
            preview = protocol.preview({"request": _request()})
            protocol.export({"request": _request(), "confirmed": True,
                             "confirmation_token": preview["confirmation_token"]})
        protocol._prune_memory()
        self.assertLessEqual(len(protocol._artifacts), 2)

    def test_parallel_previews_keep_request_local_provider(self):
        class SnapshotProvider:
            source_kind = "synthetic"
            formal_data_available = True

            def __init__(self, value):
                self.value = value

            def resolve(self, _selector):
                return []

            def materialize_with_exports(self, request):
                bundle = {"request": request, "records": [{"value": self.value}],
                          "selected_datasets": [], "quality_profile": {"datasets": [],
                          "progress_exclusions": {"excluded_record_count": 0}},
                          "provenance": {"source_kind": self.source_kind},
                          "manifest": {"record_count": 1, "bundle_id": str(self.value)},
                          "safety_flags": {}, "warnings": [], "missing_information": []}
                return bundle, {"json": json.dumps(bundle)}

        class SequencedProvider(SnapshotProvider):
            def __init__(self):
                super().__init__(0)
                self.counter = 0
                self.lock = threading.Lock()
                self.barrier = threading.Barrier(2)

            def refresh(self):
                with self.lock:
                    self.counter += 1
                    value = self.counter
                self.barrier.wait()
                return SnapshotProvider(value)

        protocol = AnalysisExportProtocolService(SequencedProvider())
        results = []

        def run():
            preview = protocol.preview({"request": _request()})
            results.append(protocol.export({"request": _request(), "confirmed": True,
                                            "confirmation_token": preview["confirmation_token"]}))

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        values = {json.loads(protocol.artifact(item["artifact_id"], "json")[1])["records"][0]["value"]
                  for item in results}
        self.assertEqual(values, {1, 2})

    def test_concurrent_confirm_consumes_same_token_once(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        preview = protocol.preview({"request": _request()})
        token = preview["confirmation_token"]
        start = threading.Barrier(2)
        results = []
        errors = []

        def confirm():
            try:
                start.wait()
                results.append(protocol.export({
                    "request": _request(),
                    "confirmed": True,
                    "confirmation_token": token,
                }))
            except BaseException as exc:  # report worker failures in the test thread
                errors.append(repr(exc))

        threads = [threading.Thread(target=confirm) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(item["status"] == "bundle_ready" for item in results), 1)
        self.assertEqual(sum(item["status"] == "confirmation_mismatch" for item in results), 1)
        self.assertEqual(len(protocol._previews), 0)
        self.assertEqual(len(protocol._artifacts), 1)

    def test_concurrent_preview_confirm_and_artifact_access_is_bounded(self):
        temp, root, tracker_path, dictionary_path = self._files()
        self.addCleanup(temp.cleanup)
        protocol = AnalysisExportProtocolService(FormalReadOnlyDataSource(tracker_path, dictionary_path))
        protocol.MAX_PREVIEWS = 8
        protocol.MAX_ARTIFACTS = 4
        start = threading.Barrier(4)
        errors = []
        statuses = []
        result_lock = threading.Lock()

        def run(worker):
            try:
                start.wait()
                for index in range(10):
                    request = _request()
                    request["datasets"][0]["dataset_id"] = f"body_check_{worker}_{index}"
                    preview = protocol.preview({"request": request, "preview_context_id": f"{worker}-{index}"})
                    if preview["status"] != "preview_ready":
                        with result_lock:
                            statuses.append(preview["status"])
                        continue
                    result = protocol.export({
                        "request": request,
                        "confirmed": True,
                        "confirmation_token": preview["confirmation_token"],
                        "preview_context_id": f"{worker}-{index}",
                    })
                    with result_lock:
                        statuses.append(result["status"])
                    if result["status"] == "bundle_ready":
                        protocol.artifact(result["artifact_id"], "json")
            except BaseException as exc:  # report worker failures in the test thread
                with result_lock:
                    errors.append(repr(exc))

        threads = [threading.Thread(target=run, args=(worker,)) for worker in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(statuses), 40)
        self.assertTrue(all(status in {"bundle_ready", "confirmation_mismatch"} for status in statuses))
        with protocol._store_lock:
            protocol._prune_memory_locked()
            self.assertLessEqual(len(protocol._previews), protocol.MAX_PREVIEWS)
            self.assertLessEqual(len(protocol._artifacts), protocol.MAX_ARTIFACTS)


if __name__ == "__main__":
    unittest.main()
