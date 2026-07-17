"""Anonymous Core pilot coverage; never reads or writes formal data/."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledger_commands import LedgerCommandError, LedgerCommandService
import ledger_commands
from fitness_ledger_core.analysis_export import build_export
from fitness_ledger_core.custom_metric_quality import collect_custom_metric_issues
from fitness_ledger_core.shared_view_models import LedgerViewModels


def make_service(root: Path) -> LedgerCommandService:
    tracker = root / "tracker.json"; dictionary = root / "movement_dictionary.json"
    tracker.write_text(json.dumps({"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []}), encoding="utf-8")
    dictionary.write_text(json.dumps({"version": "1.0", "movements": []}), encoding="utf-8")
    return LedgerCommandService(tracker, dictionary, root / "backup", lambda *_args: {})


def expect(code, fn):
    try: fn()
    except LedgerCommandError as exc:
        assert exc.code == code, (exc.code, code)
    else: raise AssertionError(f"expected {code}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fl-custom-metric-") as name:
        root = Path(name); service = make_service(root)
        service.create_custom_metric({"metric_id": "daily_steps", "label": "Steps", "unit": "steps", "number_format": "integer", "decimal_places": 0, "order": 1})
        service.create_custom_metric({"metric_id": "daily_water", "label": "Water", "unit": "L", "number_format": "decimal", "decimal_places": 1, "order": 2})
        expect("METRIC_ID_IMMUTABLE", lambda: service.update_custom_metric("daily_steps", {"metric_id": "other"}))
        assert service.set_daily_custom_metric_value("daily_steps", "2026-07-16", "5200")["status"] == "CREATED"
        assert service.set_daily_custom_metric_value("daily_steps", "2026-07-16", 5200.0)["status"] == "NO_CHANGES"
        expect("METRIC_INTEGER_REQUIRED", lambda: service.set_daily_custom_metric_value("daily_steps", "2026-07-17", 1.5))
        expect("METRIC_VALUE_NONFINITE", lambda: service.set_daily_custom_metric_value("daily_steps", "2026-07-17", "NaN"))
        service.set_daily_custom_metric_value("daily_water", "2026-07-16", "2.5")
        before_failed_write = (root / "tracker.json").read_bytes()
        original_write = ledger_commands._write_json_atomic
        ledger_commands._write_json_atomic = lambda path, value: (_ for _ in ()).throw(OSError("injected"))
        try:
            expect("CUSTOM_METRIC_WRITE_FAILED", lambda: service.update_custom_metric("daily_steps", {"label": "Injected"}))
        finally:
            ledger_commands._write_json_atomic = original_write
        assert (root / "tracker.json").read_bytes() == before_failed_write
        expect("METRIC_INACTIVE_NO_NEW_VALUE", lambda: (service.set_custom_metric_status("daily_water", "inactive"), service.set_daily_custom_metric_value("daily_water", "2026-07-17", 1.0)))
        service.set_custom_metric_status("daily_water", "archived")
        expect("METRIC_ARCHIVED_READ_ONLY", lambda: service.set_daily_custom_metric_value("daily_water", "2026-07-16", 3.0))
        service.upsert_custom_metric_placement("steps_home", {"metric_id": "daily_steps", "page": "Home", "slot": "top_aux", "mode": "latest_value", "order": 1, "enabled": True})
        service.upsert_custom_metric_placement("steps_daily", {"metric_id": "daily_steps", "page": "Daily Entry", "slot": "right_note", "mode": "input", "order": 2, "enabled": True})
        service.upsert_custom_metric_placement("steps_trend", {"metric_id": "daily_steps", "page": "Analysis", "slot": "card_extra", "mode": "trend_30d", "order": 3, "enabled": True})
        service.set_daily_custom_metric_value("daily_steps", "2026-07-17", 6000)
        assert service.undo_last_write()["undone"] is True
        assert "2026-07-17" not in service.load_state()[0]["custom_metric_values"]["daily_steps"]
        views = LedgerViewModels(root / "tracker.json", root / "movement_dictionary.json")
        assert views.custom_metric_daily_entry("2026-07-16")[0]["value"] == 5200
        assert views.custom_metric_daily_archive("2026-07-16")[0]["metric_id"] == "daily_steps"
        assert views.custom_metric_history("daily_steps")["valid_days"] == 1
        assert len(views.custom_metric_placements(page="Home")) == 1
        export = build_export(views, {"days": 36500})
        assert "custom_metrics" in export["payload"] and "daily_steps" in export["json"] and "Custom Daily Metrics" in export["markdown"]
        database, _dictionary = service.load_state()
        assert not collect_custom_metric_issues(database)
        # Corrupt one definition: native and other metric projections remain readable.
        database["custom_metric_definitions"]["daily_water"]["number_format"] = "bad"
        root.joinpath("tracker.json").write_text(json.dumps(database), encoding="utf-8")
        assert views.custom_metric_definitions()[0]["metric_id"] == "daily_steps"
        assert any(item["target_id"] == "daily_water" for item in collect_custom_metric_issues(database))
        assert service.remove_daily_custom_metric_value("daily_steps", "2026-07-16")["changed"] is True
        assert service.remove_daily_custom_metric_value("daily_steps", "2026-07-16")["status"] == "NO_CHANGES"
    print("custom daily metric core: PASS")


if __name__ == "__main__": main()
