"""Isolated fail-closed tests for the formal JSON write boundary."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledger_commands import LedgerCommandError, LedgerCommandService


PARSED = {
    "id": "audit-record",
    "date": "2026-09-01",
    "raw": "audit-only input",
    "body": {"weight": 70},
    "diet": {"calories": 2000, "protein": 150, "carbs": 200, "fat": 60},
    "training": {"split": "", "movements": []},
}


def run_case(case: str) -> None:
    with TemporaryDirectory(prefix="fl-fail-closed-") as temporary:
        root = Path(temporary)
        tracker = root / "tracker.json"
        dictionary = root / "movement_dictionary.json"
        tracker.write_text(
            '{"daily_records":[],"diet_records":[],"training_sessions":[],"movements":{},"raw_entries":[]}',
            encoding="utf-8",
        )
        dictionary.write_text('{"version":"1.0","movements":[]}', encoding="utf-8")
        target = tracker if case.startswith("tracker") else dictionary
        if case.endswith("missing"):
            target.unlink()
        else:
            target.write_text("{broken", encoding="utf-8")
        service = LedgerCommandService(
            tracker,
            dictionary,
            root / "backups",
            lambda _raw, _database, _dictionary: {},
        )
        try:
            service.save(PARSED)
        except LedgerCommandError as error:
            assert error.code == "SAVE_FAILED"
            assert error.details["rolled_back"] is True
        else:
            raise AssertionError(f"{case} unexpectedly saved")
        assert target.exists() is (not case.endswith("missing"))
        if target.exists():
            assert target.read_text(encoding="utf-8") == "{broken"


def main() -> None:
    for case in (
        "tracker_missing",
        "tracker_corrupt",
        "dictionary_missing",
        "dictionary_corrupt",
    ):
        run_case(case)
    print("FITNESS_LEDGER_FAIL_CLOSED_WRITE_OK")


if __name__ == "__main__":
    main()
