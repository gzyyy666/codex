from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for path in (PROJECT, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from custom_movement_merge_test import SOURCE_ID, TARGET_ID, fixture_values  # noqa: E402
from ledger_commands import LedgerCommandError  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def signature(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_web_service(root: Path, tracker_value: dict | None = None, dictionary_value: dict | None = None):
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    default_tracker, default_dictionary = fixture_values()
    write_json(tracker, tracker_value or default_tracker)
    write_json(dictionary, dictionary_value or default_dictionary)
    return LedgerWebService(tracker, dictionary, backups), tracker, dictionary, backups


def get_json(base: str, path: str) -> tuple[int, object]:
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def post_json(base: str, path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def serve(service: LedgerWebService):
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def stop(server, thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_candidates_and_preview() -> None:
    tracker, dictionary = fixture_values()
    dictionary["movements"].extend([
        {
            "movement_id": "CUSTOM_099",
            "display_name": "另一个临时动作",
            "aliases": ["Temp movement"],
            "muscle_group": "Back",
            "active": True,
        },
        {
            "movement_id": "BACK_099",
            "display_name": "停用正式动作",
            "aliases": [],
            "muscle_group": "Back",
            "active": False,
        },
        {
            "movement_id": "BACK_100",
            "display_name": "临时正式动作",
            "aliases": [],
            "muscle_group": "Back",
            "active": True,
            "temporary": True,
        },
    ])
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-ui-preview-") as temp:
        service, tracker_file, dictionary_file, backups = make_web_service(Path(temp), tracker, dictionary)
        rows = service.dictionary_entries()
        assert next(item for item in rows if item["movement_id"] == SOURCE_ID)["is_custom"] is True
        assert next(item for item in rows if item["movement_id"] == TARGET_ID)["is_custom"] is False

        candidates = service.canonical_movement_candidates(SOURCE_ID)
        candidate_ids = {item["movement_id"] for item in candidates}
        assert TARGET_ID in candidate_ids and "CHEST_001" in candidate_ids
        assert SOURCE_ID not in candidate_ids and "CUSTOM_099" not in candidate_ids
        assert "BACK_099" not in candidate_ids and "BACK_100" not in candidate_ids
        assert set(candidates[0]) == {
            "movement_id", "display_name", "english_name", "aliases", "muscle_group", "history_count"
        }
        assert all("history" not in item and "notes" not in item for item in candidates)
        assert [item["movement_id"] for item in service.canonical_movement_candidates(SOURCE_ID, "平板卧推")] == ["CHEST_001"]

        before = (signature(tracker_file), signature(dictionary_file))
        preview = service.preview_custom_movement_merge({"source_id": SOURCE_ID, "target_id": TARGET_ID})
        assert preview["operation"] == "CUSTOM_TO_CANONICAL_MOVEMENT_MERGE"
        assert preview["can_execute"] is True and preview["plan_identity"]
        assert preview["history"]["source_history_count"] == 2
        assert preview["references"]["migratable_count"] > 0
        assert preview["aliases"]["to_add"] and preview["warnings"]
        assert preview["blockers"] == []
        assert (signature(tracker_file), signature(dictionary_file)) == before
        assert not backups.exists()

        server, thread, base = serve(service)
        try:
            status, http_candidates = get_json(
                base,
                "/api/movements/canonical-candidates?"
                + urllib.parse.urlencode({"source_id": SOURCE_ID, "q": "Lat Pulldown"}),
            )
            assert status == 200 and [item["movement_id"] for item in http_candidates] == [TARGET_ID]
            status, http_preview = post_json(
                base,
                "/api/movements/custom-merge/preview",
                {"source_id": SOURCE_ID, "target_id": TARGET_ID},
            )
            assert status == 200 and http_preview["plan_identity"] == preview["plan_identity"]
            status, required = post_json(
                base,
                "/api/movements/custom-merge/execute",
                {"source_id": SOURCE_ID, "target_id": TARGET_ID},
            )
            assert status == 400 and required["code"] == "PREVIEW_REQUIRED"
        finally:
            stop(server, thread)


def test_stale_blocked_failure_and_success() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-ui-stale-") as temp:
        service, _tracker, dictionary, _backups = make_web_service(Path(temp))
        preview = service.preview_custom_movement_merge({"source_id": SOURCE_ID, "target_id": TARGET_ID})
        value = json.loads(dictionary.read_text(encoding="utf-8"))
        next(item for item in value["movements"] if item["movement_id"] == TARGET_ID)["notes"] = "changed"
        write_json(dictionary, value)
        try:
            service.execute_custom_movement_merge({
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "plan_identity": preview["plan_identity"],
            })
            raise AssertionError("stale preview unexpectedly executed")
        except LedgerCommandError as error:
            assert error.code == "PREVIEW_STALE"

    tracker, dictionary = fixture_values()
    dictionary["movements"].append({
        "movement_id": "BACK_777",
        "display_name": "Alias Owner",
        "aliases": ["Old Pulldown"],
        "muscle_group": "Back",
        "active": True,
    })
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-ui-blocked-") as temp:
        service, tracker_file, dictionary_file, _backups = make_web_service(Path(temp), tracker, dictionary)
        before = (signature(tracker_file), signature(dictionary_file))
        preview = service.preview_custom_movement_merge({"source_id": SOURCE_ID, "target_id": TARGET_ID})
        assert preview["can_execute"] is False
        assert "ALIAS_OWNERSHIP_CONFLICT" in {item["code"] for item in preview["blockers"]}
        try:
            service.execute_custom_movement_merge({
                "source_id": SOURCE_ID,
                "target_id": TARGET_ID,
                "plan_identity": preview["plan_identity"],
            })
            raise AssertionError("blocked preview unexpectedly executed")
        except LedgerCommandError as error:
            assert error.code == "MIGRATION_BLOCKED" and error.details["blockers"]
        assert (signature(tracker_file), signature(dictionary_file)) == before

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-ui-failure-") as temp:
        service, _tracker, _dictionary, _backups = make_web_service(Path(temp))
        original = service.commands.merge_custom_movement

        def fail(*_args):
            raise LedgerCommandError(
                "Movement migration failed; both formal files were restored.",
                "MIGRATION_FAILED",
                {"rolled_back": True, "rollback_errors": [], "failed_stage": "tracker_write"},
            )

        service.commands.merge_custom_movement = fail
        server, thread, base = serve(service)
        try:
            status, payload = post_json(
                base,
                "/api/movements/custom-merge/execute",
                {"source_id": SOURCE_ID, "target_id": TARGET_ID, "plan_identity": "fixture-plan"},
            )
            assert status == 500 and payload["code"] == "MIGRATION_FAILED"
            assert payload["details"]["rolled_back"] is True
        finally:
            service.commands.merge_custom_movement = original
            stop(server, thread)

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-custom-ui-success-") as temp:
        service, tracker_file, dictionary_file, _backups = make_web_service(Path(temp))
        preview = service.preview_custom_movement_merge({"source_id": SOURCE_ID, "target_id": TARGET_ID})
        result = service.execute_custom_movement_merge({
            "source_id": SOURCE_ID,
            "target_id": TARGET_ID,
            "plan_identity": preview["plan_identity"],
        })
        assert result["status"] == "UPDATED"
        assert result["migrated_history_count"] == 2 and result["migrated_reference_count"] > 0
        assert result["raw_entries_unchanged"] is True and result["validation"]["ok"] is True
        assert result["undo"]["available"] is True
        assert SOURCE_ID not in {item["movement_id"] for item in service.dictionary_entries()}
        assert service.commands.undo_status()["available"] is True
        undo = service.undo_last_write()
        assert undo["undone"] is True
        assert SOURCE_ID in {item["movement_id"] for item in service.dictionary_entries()}
        assert signature(tracker_file) and signature(dictionary_file)


def test_frontend_contract() -> None:
    app = (PROJECT / "web_desktop" / "frontend" / "app.js").read_text(encoding="utf-8")
    styles = (PROJECT / "web_desktop" / "frontend" / "styles.css").read_text(encoding="utf-8")
    server = (PROJECT / "web_desktop" / "backend" / "server.py").read_text(encoding="utf-8")
    assert "item.is_custom===true" in app and "data-custom-merge-open" in app
    assert 'name="muscle_group"' in app and "dictionary-identity-action" in app
    assert "/api/movements/canonical-candidates" in app
    assert 'type="search"' in app and 'name="target_id"' not in app
    assert "data-custom-merge-target" in app and "movementMergeIdentity" in app
    assert "/api/movements/custom-merge/preview" in app
    assert "source_history_count" in app and "migratable_count" in app and "aliases.to_add" in app
    assert "plan.warnings" in app and "plan.blockers" in app and "!plan.can_execute||!plan.plan_identity" in app
    assert "flow.submitting" in app and "plan_identity:plan.plan_identity" in app
    for code in ("PREVIEW_REQUIRED", "PREVIEW_STALE", "MIGRATION_BLOCKED", "MIGRATION_FAILED"):
        assert code in app
    assert "navigate('movements',{movement_id:result.target_id})" in app
    assert "await loadArchiveHealth()" in app and "state.movementMerge=null" in app
    assert "movement-merge-modal" in styles and "movement-merge-confirm.is-disabled" in styles
    assert "preview_merge_custom_movement" in server and "merge_custom_movement" in server
    assert "_write_json_atomic" not in server


def main() -> None:
    test_candidates_and_preview()
    test_stale_blocked_failure_and_success()
    test_frontend_contract()
    print("FITNESS_LEDGER_CUSTOM_MOVEMENT_MERGE_UI_OK")


if __name__ == "__main__":
    main()
