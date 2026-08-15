"""Run an isolated phone PWA review with anonymous Data Module examples."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import webbrowser
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore  # noqa: E402
from mobile_viewer.app import create_app  # noqa: E402
from mobile_viewer.data_access import LedgerDataAccess  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def module_record(module_id: str, category_id: str, date: str, value: float, unit: str = "") -> dict:
    return {
        "record_id": f"review-{module_id}-{date}",
        "module_id": module_id,
        "category_id": category_id,
        "record_kind": "scalar",
        "date": date,
        "value": value,
        "actual_unit": unit,
        "definition_version": 1,
        "definition_snapshot": {},
        "source": "anonymous-review-fixture",
    }


def prepare_fixture(root: Path) -> tuple[Path, Path, Path]:
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    registry = root / "data_module_definitions.json"
    write_json(tracker, {
        "daily_records": [{"Date": "2026-08-15", "Weight (kg)": 70.0, "Bowel Movement": "正常", "Training": "背", "Cardio": "步行 30 分钟", "Notes": "匿名展示数据"}],
        "diet_records": [{"Date": "2026-08-15", "Calories (kcal)": 2050, "Protein (g)": 150, "Carbs (g)": 220, "Fat (g)": 62, "Food Summary": "匿名饮食摘要"}],
        "training_sessions": [{"Date": "2026-08-15", "Split": "背部训练", "Standardized Summary": "引体向上、划船", "Notes": "匿名训练摘要"}],
        "movements": {},
        "raw_entries": [],
        "data_module_records": [
            module_record("waist_cm", "body", "2026-08-15", 82.5, "cm"),
            module_record("creatine_g", "diet", "2026-08-14", 5, "g"),
            module_record("training_readiness", "training", "2026-08-13", 8),
            module_record("sleep_score", "extension", "2026-08-15", 7),
            module_record("grip_readiness", "extension", "2026-08-15", 6),
        ],
    })
    write_json(dictionary, {"version": "1.0", "movements": []})
    DataModuleDefinitionStore.initialize(
        registry,
        PROJECT / "tools" / "fixtures" / "data_modules" / "pwa_mobile_registry.json",
        backup_dir=root / "definition_backups",
    )
    return tracker, dictionary, registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-mobile-review-") as temp:
        tracker, dictionary, registry = prepare_fixture(Path(temp))
        app = create_app(LedgerDataAccess(tracker, dictionary), registry)
        url = f"http://127.0.0.1:{args.port}/pwa/"
        print("Fitness Ledger Phone Data Module Review")
        print(f"URL: {url}")
        print("Fixture: anonymous and temporary; no formal tracker or Cloud mutation")
        print("Stop: Ctrl+C")
        if args.open:
            webbrowser.open(url)
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
