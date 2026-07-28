"""Deterministic QueryScope entity-resolution checks on anonymous catalog cards."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fitness_ledger_core.query_scope import BODY_PART_TERMS, QueryScopeResolver
from fitness_ledger_core.intelligent_export_models import DataCatalog, MovementCard

def main() -> None:
    card = MovementCard("CHEST_006", "卧推", ["卧推"], "Chest", "CHEST", 4, 4, 0, "2026-01-01", "2026-07-20", "2026-07-20", "2026-07-20", {}, "sufficient", {}, 1)
    catalog = DataCatalog("c", "s", "", {"start": "2026-01-01", "end": "2026-07-20"}, "2026-07-20", [], [card], [], [])
    resolver = QueryScopeResolver(catalog)
    assert set(BODY_PART_TERMS) == {"CHEST", "BACK", "SHOULDER", "ARMS", "CORE", "LEGS"}
    cases = {"胸部训练": ["CHEST"], "胸肌表现": ["CHEST"], "肩部训练": ["SHOULDER"], "后束最近怎么样": ["SHOULDER"], "背部训练": ["BACK"], "二头训练": ["ARMS"], "三头训练": ["ARMS"], "腹部训练": ["CORE"], "腿部训练": ["LEGS"], "看看我最近减脂怎么样": []}
    for request, expected in cases.items():
        assert resolver.resolve(request).target_body_part_ids == expected, request
    scope = resolver.resolve("卧推最近怎么样")
    assert scope.explicit_movement_ids == ["CHEST_006"] and not scope.target_body_part_ids
    scope = resolver.resolve("卧推和其他胸部动作")
    assert scope.explicit_movement_ids == ["CHEST_006"] and scope.target_body_part_ids == ["CHEST"]
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_QUERY_SCOPE_OK")

if __name__ == "__main__":
    main()
