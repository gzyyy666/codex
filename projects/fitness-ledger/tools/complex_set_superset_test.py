from __future__ import annotations

import copy
import importlib.machinery
import json
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fitness_ledger_core.record_relations import validate_relations
from fitness_ledger_core.analysis_export_materializer import AnonymousFixtureMaterializer
from fitness_ledger_core.shared_view_models import LedgerViewModels
from fitness_ledger_core.training_structure import (
    format_set_item,
    parse_segmented_blocks,
    parse_superset_directives,
    relation_specs,
    set_total_reps,
    set_volume,
)
from fitness_ledger_core.training_organization import resolve_session_theme_ids
from ledger_commands import LedgerCommandError, LedgerCommandService


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parsed(raw: str, *, issues: list[dict] | None = None, directives: list[dict] | None = None) -> dict:
    return {
        "id": "pending-structure",
        "date": "2099-01-01",
        "raw": raw,
        "body": {"weight": 70, "bowel_movement": "yes", "notes": ""},
        "diet": {"calories": 2000, "protein": 140, "carbs": 200, "fat": 60, "notes": ""},
        "training": {
            "split": "Chest + Shoulder",
            "raw": raw,
            "standardized_summary": "",
            "notes": "",
            "_structure_issues": issues or [],
            "_superset_directives": directives or [],
            "movements": [
                {"name": "Press A", "movement_id": "A", "order": 1, "sets": [{"segments": [{"weight": 7.5, "reps": 6}, {"weight": 5, "reps": 8}], "sets": 3}]},
                {"name": "Press B", "movement_id": "B", "order": 2, "sets": [{"weight": 30, "reps": 12, "sets": 3}]},
            ],
        },
    }


def relation_neutral_signature(session: dict) -> dict:
    items = session.get("movement_items", []) or []
    item_rows = []
    for item in items:
        sets = item.get("sets", []) or []
        item_rows.append({
            "identity": item.get("movement_instance_id") or item.get("id"),
            "order": item.get("order_in_session", item.get("order")),
            "set_count": sum(int(set_item.get("sets", 1) or 1) for set_item in sets),
            "volume": round(sum(set_volume(set_item) for set_item in sets), 2),
        })
    return {
        "movement_count": len(items),
        "set_count": sum(row["set_count"] for row in item_rows),
        "movement_volume": [row["volume"] for row in item_rows],
        "session_volume": round(sum(row["volume"] for row in item_rows), 2),
        "order": [row["order"] for row in item_rows],
        "identity": [row["identity"] for row in item_rows],
    }


def main() -> None:
    themes = [
        {"theme_id": "chest", "display_name": "胸", "aliases": ["胸部"]},
        {"theme_id": "shoulders", "display_name": "肩", "aliases": ["肩部"]},
    ]
    assert resolve_session_theme_ids("胸肩", themes) == ["chest", "shoulders"]
    assert resolve_session_theme_ids("胸、肩", themes) == ["chest", "shoulders"]
    assert resolve_session_theme_ids("未配置主题", themes) == []

    blocks, issues = parse_segmented_blocks("(7.5+5)-(6+8)-3")
    assert not issues and len(blocks) == 1 and len(blocks[0]["segments"]) == 2
    assert set_volume(blocks[0]) == 255 and set_total_reps(blocks[0]) == 42
    assert format_set_item(blocks[0]) == "7.5kg × 6 + 5kg × 8 × 3组"
    fullwidth_blocks, fullwidth_issues = parse_segmented_blocks("（7.5＋5）－（6＋8）－3")
    assert not fullwidth_issues and fullwidth_blocks == blocks

    fixture_path = PROJECT / "tools" / "fixtures" / "analysis_export_anonymous" / "fixture.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["datasets"]["movement_progress"].append({
        "date": "2099-12-30", "movement_id": "m_synthetic_press", "movement_name": "Synthetic Press",
        "body_part": "chest", "variant": "complex", "order": 1,
        "sets": [{"segments": blocks[0]["segments"], "sets": 3}], "segments": [blocks[0]["segments"]],
        "set_count": 3, "segment_count": 2, "total_reps": 42, "volume": 255,
        "organization_relations": [{"id": "superset:anonymous:A", "type": "superset", "members": ["mi-1", "mi-2"]}],
    })
    export = AnonymousFixtureMaterializer(fixture).materialize({
        "request_version": "1.1", "purpose": "complex set export", "raw": False,
        "datasets": [{"dataset_id": "movement", "type": "movement_progress", "time_range": {"mode": "explicit_range", "start": "2099-12-30", "end": "2099-12-30"}, "filters": {}, "fields": ["date", "sets", "segments", "set_count", "segment_count", "total_reps", "volume", "organization_relations"]}],
        "output": {"formats": ["json"]},
    })
    exported = next(row for row in export["records"] if row.get("volume") == 255)
    assert exported["segments"][0][1]["reps"] == 8 and exported["organization_relations"][0]["type"] == "superset"

    mismatch, mismatch_issues = parse_segmented_blocks("(7.5+5+2.5)-(6+8)-3")
    assert mismatch == [] and mismatch_issues[0]["code"] == "SEGMENT_COUNT_MISMATCH"
    unequal, unequal_issues = parse_segmented_blocks("sets: 7.5x6+5x8; 7.5x6+5x7; 7.5x5+5x8")
    assert not unequal_issues and len(unequal) == 3 and all(row["sets"] == 1 for row in unequal)

    directives, directive_issues = parse_superset_directives("superset: A = movement 1, movement 2")
    assert not directive_issues and directives == [{"label": "A", "orders": [1, 2]}]
    fullwidth_directives, fullwidth_directive_issues = parse_superset_directives("superset：A＝movement 1，movement 2")
    assert not fullwidth_directive_issues and fullwidth_directives == directives
    items = [{"id": "i1", "movement_instance_id": "i1", "order": 1}, {"id": "i2", "movement_instance_id": "i2", "order": 2}]
    relations, relation_issues = relation_specs(directives, items, "s1")
    assert not relation_issues and relations[0]["members"] == ["i1", "i2"]

    loader = importlib.machinery.SourceFileLoader("fitness_ledger_stable_app_test", str(PROJECT / "stable_app.pyw"))
    stable = loader.load_module()
    assert stable.extract_load_blocks("60 x 5 x 3") == [{"weight": 60.0, "reps": 5, "sets": 3}]
    assert stable.extract_load_blocks("(7.5+5)-(6+8)-3")[0]["segments"] == blocks[0]["segments"]
    assert stable.extract_load_blocks("（7.5＋5）－（6＋8）－3")[0]["segments"] == blocks[0]["segments"]
    assert stable.extract_load_blocks("(7.5+5+2.5)-(6+8)-3") == []
    parser = stable.FitnessTrackerApp.__new__(stable.FitnessTrackerApp)
    parser.movement_definitions_by_alias = {}
    bare_training = parser.parse_entry("3. y举\n（7.5＋5）－（6＋8）－3")["training"]
    assert len(bare_training["movements"]) == 1 and bare_training["movements"][0]["sets"][0]["segments"] == blocks[0]["segments"]

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-structure-") as root:
        root = Path(root)
        tracker = root / "tracker.json"
        dictionary = root / "dictionary.json"
        write(tracker, {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []})
        write(dictionary, {"version": "1", "movements": [
            {"movement_id": "A", "display_name": "Press A", "aliases": ["Press A"], "active": True},
            {"movement_id": "B", "display_name": "Press B", "aliases": ["Press B"], "active": True},
        ]})
        service = LedgerCommandService(tracker, dictionary, root / "backups", lambda raw, *_: parsed(raw, directives=directives))
        result = service.save(service.parse("structured")["review"])
        assert result["status"] == "CREATED"
        stored = json.loads(tracker.read_text(encoding="utf-8"))
        session = stored["training_sessions"][0]
        assert session["organization_relations"][0]["type"] == "superset"
        assert session["movement_items"][0]["sets"][0]["segments"]
        relation_free = copy.deepcopy(session)
        relation_free.pop("organization_relations", None)
        relation_only = copy.deepcopy(relation_free)
        relation_only["organization_relations"] = copy.deepcopy(session["organization_relations"])
        assert relation_neutral_signature(relation_free) == relation_neutral_signature(relation_only)
        assert all("organization_relations" not in item for item in session["movement_items"])
        assert not validate_relations(stored, json.loads(dictionary.read_text(encoding="utf-8")))
        before = tracker.read_bytes()
        try:
            service.save(service.parse("bad")["review"] | {"training": {**service.parse("bad")["review"]["training"], "_structure_issues": [{"code": "SEGMENT_COUNT_MISMATCH", "message": "mismatch"}]}})
        except LedgerCommandError as error:
            assert error.code == "SEGMENT_COUNT_MISMATCH"
        else:
            raise AssertionError("mismatch should be rejected before write")
        assert tracker.read_bytes() == before

        views = LedgerViewModels(tracker, dictionary)
        movement = views.movement_history_by_id("A")
        assert movement["history"][0]["metrics"]["volume"] == 255
        relation_context = movement["history"][0]["organization_relations"][0]
        assert relation_context["member_order"] == 1 and relation_context["member_count"] == 2
        assert relation_context["co_members"][0]["movement_name"] == "Press B"
        assert relation_context["co_members"][0]["relation_order"] == 2
        archive = views.training_archive()
        assert len(archive) == 1 and archive[0]["id"] == session["id"]
        assert len(archive[0]["movement_refs"]) == 2
        assert {ref["training_session_id"] for ref in archive[0]["movement_refs"]} == {session["id"]}
        assert archive[0]["movement_refs"][0]["organization_relations"][0]["co_members"]

    print("FITNESS_LEDGER_COMPLEX_SET_SUPERSET_OK")


if __name__ == "__main__":
    main()
