from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from tools.archive_navigation_test import fixture  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


REVIEW_RAW = """2099-01-02
weight: 70.0
bowel: yes
calories: 1800
protein: 130
carbs: 180
fat: 55
training: chest
1. Bench Press
115kg x 8 x 2
cardio:
none
diet:
test meal
notes:
Anonymous movement cache review.
"""


def main() -> None:
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-movement-cache-review-")
    root = Path(temp.name)
    tracker, dictionary = fixture()
    (root / "tracker.json").write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
    (root / "movement_dictionary.json").write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
    service = LedgerWebService(root / "tracker.json", root / "movement_dictionary.json", root / "backups")
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Fitness Ledger anonymous movement cache review: http://127.0.0.1:{server.server_port}/#movements", flush=True)
    print("Use this Daily Entry sample:", flush=True)
    print(REVIEW_RAW, flush=True)
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        temp.cleanup()


if __name__ == "__main__":
    main()
