"""Anonymous DateIntent contract and deterministic resolver tests."""
from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.data_catalog import DataCatalogBuilder, DateRangeResolver, resolve_windows
from fitness_ledger_core.intelligent_export_models import ContractError, DateIntent, IntentSpec
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture, intent as intent_fixture


def make_intent(date_intent: dict) -> IntentSpec:
    raw = dict(intent_fixture()); raw["date_intent"] = date_intent
    return IntentSpec.from_dict(raw)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-date-") as name:
        tracker, dictionary = fixture(Path(name))
        catalog = DataCatalogBuilder(LedgerViewModels(tracker, dictionary)).build()
        resolver = DateRangeResolver()
        valid = [
            {"mode": "relative", "relative_range": "recent_8_weeks", "comparison_needed": True, "raw_date_mentions": []},
            {"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": ["7月1日到7月15日"]},
            {"mode": "unspecified", "relative_range": None, "comparison_needed": False, "raw_date_mentions": []},
            {"mode": "all_available", "relative_range": "all_available", "comparison_needed": False, "raw_date_mentions": []},
        ]
        for raw in valid:
            DateIntent.from_dict(raw)
        for raw in (
            {"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": [], "start_date": "2026-07-01"},
            {"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": [], "end_date": "2026-07-15"},
            {"mode": "relative", "relative_range": None, "comparison_needed": False, "raw_date_mentions": []},
            {"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": []},
            {"mode": "unknown", "relative_range": None, "comparison_needed": False, "raw_date_mentions": []},
            {"mode": "unspecified", "relative_range": None, "comparison_needed": False, "raw_date_mentions": [], "extra": True},
        ):
            try:
                DateIntent.from_dict(raw)
            except ContractError:
                pass
            else:
                raise AssertionError("invalid DateIntent accepted")

        cases = [
            ("2026-07-01", "explicit", 1),
            ("2026/07/01", "explicit", 1),
            ("2026年7月1日", "explicit", 1),
            ("7月1日", "explicit", 1),
            ("7月1日到7月15日", "explicit", 1),
            ("最近", "relative", 2),
            ("最近四周", "relative", 1),
            ("最近两个月", "relative", 2),
            ("这几个月", "relative", 2),
            ("全部历史", "all_available", 1),
            ("June 1, 2026", "explicit", 0),
            ("from June to July", "explicit", 1),
        ]
        for request, mode, expected in cases:
            raw = {"mode": mode, "relative_range": ("recent" if request == "最近" else "recent_months" if request in {"最近两个月", "这几个月"} else "all_available" if mode == "all_available" else None), "comparison_needed": False, "raw_date_mentions": [request] if mode == "explicit" else []}
            if mode == "relative" and raw["relative_range"] is None:
                raw["relative_range"] = "recent_4_weeks"
            windows = resolver.resolve(make_intent(raw), catalog, request, today=date(2026, 7, 22))
            assert len(windows) == expected, (request, windows)
            assert all(window.resolved_start <= window.resolved_end for window in windows)

        assert resolver.resolve(make_intent({"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": ["2026-06-1:"]}), catalog, "2026-06-1:", date(2026, 7, 22)) == []
        assert resolver.resolve(make_intent({"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": ["2026-13-40"]}), catalog, "2026-13-40", date(2026, 7, 22)) == []
        assert resolver.resolve(make_intent({"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": ["2025-01-01"]}), catalog, "2025-01-01", date(2026, 7, 22)) == []
        future = resolver._safe_month_day(None, "12", "1", date(2026, 7, 22), catalog.date_range["end"])
        assert future and future.year == 2025
        leap = resolver.resolve(make_intent({"mode": "explicit", "relative_range": None, "comparison_needed": False, "raw_date_mentions": ["2024-02-29"]}), catalog, "2024-02-29", date(2026, 7, 22))
        assert leap == []  # valid date, but no intersection with this anonymous catalog
        no_date = resolver.resolve(make_intent({"mode": "unspecified", "relative_range": None, "comparison_needed": False, "raw_date_mentions": []}), catalog, "没有日期", date(2026, 7, 22))
        assert no_date
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_DATE_OK")


if __name__ == "__main__":
    main()
