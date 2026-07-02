from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mobile_viewer.app import create_app


app = create_app()
client = app.test_client()

home = client.get("/")
assert home.status_code == 200
assert b"Fitness Ledger" in home.data

today_api = client.get("/api/today")
assert today_api.status_code == 200
today_payload = today_api.get_json()
assert isinstance(today_payload, dict)
assert "date" in today_payload

search_api = client.get("/api/search?q=bench&scope=all")
assert search_api.status_code == 200
search_payload = search_api.get_json()
assert isinstance(search_payload, dict)
assert "records" in search_payload
assert "movements" in search_payload

movement_api = client.get("/api/movement/bench press?limit=3")
assert movement_api.status_code == 200
movement_payload = movement_api.get_json()
assert "history" in movement_payload

page_search = client.get("/search?q=%E8%83%8C%E9%83%A8&scope=all")
assert page_search.status_code == 200

page_movement = client.get("/movement?q=%E5%BC%95%E4%BD%93%E5%90%91%E4%B8%8A&limit=5")
assert page_movement.status_code == 200

print("FITNESS_LEDGER_MOBILE_VIEWER_OK")
