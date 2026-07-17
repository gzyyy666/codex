"""Anonymous Web boundary coverage for the generic Custom Daily Metric pilot."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web_desktop.backend.server import LedgerWebService
from ledger_commands import LedgerCommandError


def make_service(root: Path) -> LedgerWebService:
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    tracker.write_text(json.dumps({"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []}), encoding="utf-8")
    dictionary.write_text(json.dumps({"version": "1.0", "movements": []}), encoding="utf-8")
    return LedgerWebService(tracker, dictionary, root / "backups")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fl-custom-metric-web-") as name:
        service = make_service(Path(name))
        service.create_custom_metric({"metric_id": "daily_steps", "label": "每日步数", "unit": "steps", "number_format": "integer", "decimal_places": 0, "order": 1})
        service.create_custom_metric({"metric_id": "daily_water", "label": "每日饮水量", "unit": "ml", "number_format": "integer", "decimal_places": 0, "order": 2})
        assert [row["metric_id"] for row in service.custom_metric_definitions()] == ["daily_steps", "daily_water"]

        failed = service.parse_entry("2026-07-14 weight 70")
        before_failed_save = json.loads(service.commands.data_file.read_text(encoding="utf-8"))
        try:
            service.save_review({
                "review_id": failed["review_id"],
                "review": failed["review"],
                "custom_metrics": [{"metric_id": "daily_steps", "date": "2026-07-14", "value": "not-an-integer"}],
            })
        except LedgerCommandError:
            pass
        else:
            raise AssertionError("invalid custom metric value must fail the complete save")
        assert json.loads(service.commands.data_file.read_text(encoding="utf-8")) == before_failed_save

        parsed = service.parse_entry("2026-07-15 weight 70")
        integrated = service.save_review({
            "review_id": parsed["review_id"],
            "review": parsed["review"],
            "custom_metrics": [{"metric_id": "daily_steps", "date": "2026-07-15", "value": "5000"}],
        })
        assert integrated["status"] in {"CREATED", "UPDATED"}
        assert integrated["custom_metrics_changed"] == 1
        assert next(row for row in service.custom_metric_daily_entry("2026-07-15") if row["metric_id"] == "daily_steps")["value"] == 5000

        parsed_two = service.parse_entry("2026-07-16 weight 70")
        integrated_two = service.save_review({
            "review_id": parsed_two["review_id"],
            "review": parsed_two["review"],
            "custom_metrics": [
                {"metric_id": "daily_steps", "date": "2026-07-16", "value": "5200"},
                {"metric_id": "daily_water", "date": "2026-07-16", "value": 1800},
            ],
        })
        assert integrated_two["custom_metrics_changed"] == 2
        entry = service.custom_metric_daily_entry("2026-07-16")
        assert {row["metric_id"] for row in entry} == {"daily_steps", "daily_water"}
        assert next(row for row in entry if row["metric_id"] == "daily_steps")["value"] == 5200

        service.upsert_custom_metric_placement({"placement_id": "steps_home", "metric_id": "daily_steps", "page": "Home", "slot": "top_aux", "mode": "latest_value", "order": 1, "enabled": True})
        service.upsert_custom_metric_placement({"placement_id": "water_body", "metric_id": "daily_water", "page": "Body", "slot": "right_note", "mode": "frequency", "order": 1, "enabled": True})
        home = service.custom_metric_placements("Home", "top_aux", "2026-07-16")
        assert home[0]["data"]["value"] == 5200
        body = service.custom_metric_placements("Body", "right_note", "2026-07-16")
        assert body[0]["data"]["valid_days"] == 1

        history = service.custom_metric_history("daily_steps", "2026-07-16", 30)
        assert history["latest_date"] == "2026-07-16" and history["latest_value"] == 5200
        assert service.custom_metric_daily_archive("2026-07-16")[0]["label"] == "每日步数"
        service.remove_custom_metric_placement({"placement_id": "steps_home"})
        assert service.custom_metric_placements("Home") == []
        assert service.custom_metric_daily_archive("2026-07-16")
        service.set_custom_metric_status({"metric_id": "daily_steps", "status": "archived"})
        assert service.custom_metric_daily_archive("2026-07-16")[0]["value"] == 5200
    print("FITNESS_LEDGER_CUSTOM_DAILY_METRIC_WEB_OK")


if __name__ == "__main__":
    main()
