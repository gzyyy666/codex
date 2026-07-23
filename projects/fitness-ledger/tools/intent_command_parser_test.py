"""Deterministic Analysis Export Command Parser protocol tests."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fitness_ledger_core.data_catalog import DataCatalogBuilder
from fitness_ledger_core.intent_compiler import AnalysisExportCommandParser, IntentCompileError, IntentCompiler
from fitness_ledger_core.shared_view_models import LedgerViewModels
from intelligent_export_core_test import fixture


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-command-parser-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build()
        parser = AnalysisExportCommandParser(IntentCompiler(views).query_scope_resolver, catalog)

        # Request-kind gate.
        for request in ("删除饮食记录", "修改上周训练记录", "同步到云端", "生成模板"):
            assert parser.parse(request).status == "unsupported_operation"
        assert parser.parse("分析最近的饮食").status == "resolved"

        # The six scope operator families bind to legal targets.
        assert {item.operator for item in parser.parse("只看体重").scope_operations} == {"only"}
        assert {item.operator for item in parser.parse("包括饮食").scope_operations} == {"include"}
        assert {item.operator for item in parser.parse("不要训练").scope_operations} == {"exclude"}
        assert parser.parse("先只看吃的，训练部分放一边").status == "resolved"
        assert parser.parse("把体重和饮食放进来，训练不用").status == "resolved"
        assert parser.parse("只看卧推表现，不分析具体动作").status == "conflict", parser.parse("只看卧推表现，不分析具体动作").to_dict()

        # Structured data and Notes are distinct layers.
        assert parser.parse("分析饮食").layers == ["structured"]
        assert parser.parse("分析饮食备注").layers == ["notes"]
        assert parser.parse("饮食 notes 和热量一起给我").layers == ["structured", "notes"]
        assert parser.parse("仅分析训练备注，不要每日总结").status == "resolved"

        # Date surface is preserved and classified without generated dates.
        assert parser.parse("看看最近的体重").date.kind == "calendar_relative"
        assert parser.parse("看看上周的体重").date.kind == "calendar_relative"
        assert parser.parse("看看2026年7月的体重").date.kind == "explicit_calendar"
        assert parser.parse("看看最近几次训练").date.kind == "record_relative"
        assert parser.parse("一整个月的体重走势").status == "clarification_required"

        # Body part is a training filter; it never creates a movement.
        shoulder = parser.parse("看看肩部训练最近怎么样")
        assert shoulder.status == "resolved" and shoulder.body_parts == ["SHOULDER"] and not shoulder.movement_mentions
        assert parser.parse("看看侧平举最近有没有进步").movement_mentions == ["侧平举"]
        assert parser.parse("看看推胸有没有进步").status == "clarification_required"

        # Raw permission and empty/conflicting scopes are fail-closed.
        assert parser.parse("追溯最近一周的原始记录").status == "resolved"
        assert "raw" in parser.parse("追溯最近一周的原始记录").layers
        assert parser.parse("只看训练，不要训练").status == "conflict"
        assert parser.parse("看看最近的情况").status == "clarification_required"

    print("FITNESS_LEDGER_INTENT_COMMAND_PARSER_OK")


if __name__ == "__main__":
    main()
