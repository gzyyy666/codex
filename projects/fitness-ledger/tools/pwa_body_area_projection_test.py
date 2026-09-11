"""Regression checks for complex-set and superset context in PWA body areas."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from complex_set_superset_browser_test import write_fixture
from mobile_viewer.app import create_app
from mobile_viewer.data_access import LedgerDataAccess


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-body-area-") as temp:
        root = Path(temp)
        write_fixture(root)
        client = create_app(LedgerDataAccess(root / "tracker.json", root / "movement_dictionary.json")).test_client()
        area = client.get("/api/pwa/read?action=bodyArea&part=chest").get_json()["data"]
        movement = next(item for item in area["movements"] if item["movement_id"] == "m_press")
        latest = movement["latest"]

        assert latest["summary"] == "7.5kg × 6 + 5kg × 8 × 3组"
        assert latest["training_session_id"] == "session-complex-superset"
        assert len(latest["organization_relations"]) == 1
        relation = latest["organization_relations"][0]
        assert relation["member_order"] == 1
        assert relation["member_count"] == 2
        assert relation["co_members"][0]["movement_name"] == "Triceps Pushdown"
        assert relation["co_members"][0]["relation_order"] == 2
        assert relation["co_members"][0]["sets_lines"] == ["30kg × 12 × 3"]
    print("pwa body-area complex/superset projection: PASS")


if __name__ == "__main__":
    main()
