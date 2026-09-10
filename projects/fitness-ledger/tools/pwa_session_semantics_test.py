"""Focused regression checks for the PWA session-based Training Record surface."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mobile_viewer.app import create_app
from mobile_viewer.data_access import MovementMatch


class FakeAccess:
    _cache = {}

    def __init__(self):
        self._sessions = [
            {
                "id": "same-day-1",
                "Date": "2026-09-10",
                "session_sequence": 1,
                "session_theme_ids": ["pull"],
                "session_theme_name": "Pull Day",
                "Split": "背",
                "Standardized Summary": "第一段训练",
                "movement_items": [
                    {"movement_id": "M1", "display_name": "动作一", "order_in_session": 2, "sets": [{"weight": 10, "reps": 8, "sets": 3}], "notes": "动作备注"},
                    {"movement_id": "CUSTOM", "display_name": "自定义动作", "order_in_session": 1, "sets": [{"weight_text": "自重", "reps": 12, "sets": 2}]},
                ],
            },
            {
                "id": "same-day-2",
                "Date": "2026-09-10",
                "session_sequence": 2,
                "session_theme_ids": ["legs"],
                "session_theme_name": "腿",
                "Split": "腿",
                "Standardized Summary": "第二段训练",
                "movement_items": [],
            },
        ]
        self._tracker_data = {
            "training_organization": {
                "session_themes": [
                    {"theme_id": "pull", "display_name": "Pull Day", "active": True},
                    {"theme_id": "legs", "display_name": "腿", "active": True},
                ],
                "movement_categories": [],
            },
            "training_sessions": self._sessions,
        }
        self._movements = {"M1": MovementMatch("M1", "动作一", "Action One", [], "Back", "", True, "")}

    def _tracker(self):
        return self._tracker_data

    def _movements_by_id(self):
        return self._movements


def main() -> None:
    client = create_app(FakeAccess()).test_client()
    records = client.get("/api/pwa/read?action=trainingRecords").get_json()["data"]
    assert len(records) == 2, "same-day sessions must remain two records"
    assert {item["id"] for item in records} == {"same-day-1", "same-day-2"}

    detail = client.get("/api/pwa/read?action=trainingDayDetail&sessionId=same-day-1").get_json()["data"]
    assert detail["session"]["id"] == "same-day-1"
    assert detail["session"]["theme_names"] == ["Pull Day"]
    assert [item["order_in_session"] for item in detail["movements"]] == [1, 2]
    assert detail["movements"][0]["movement_name"] == "自定义动作"
    assert detail["movements"][0]["summary"] == "自重 × 12 × 2"
    assert detail["movements"][1]["notes"] == "动作备注"

    detail_two = client.get("/api/pwa/read?action=trainingDayDetail&sessionId=same-day-2").get_json()["data"]
    assert detail_two["session"]["id"] == "same-day-2"
    assert detail_two["session"]["theme_names"] == ["腿"]
    assert detail_two["movements"] == []
    print("pwa session semantics regression: PASS")


if __name__ == "__main__":
    main()
