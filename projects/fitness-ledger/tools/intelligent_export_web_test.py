"""Anonymous Web contract tests for the deterministic Intelligent Export candidate."""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.intent_real_acceptance import fixture
from web_desktop.backend.server import LedgerWebService, create_server


SCENARIOS = [
    "\u5206\u6790\u6700\u8fd1\u4e00\u4e2a\u6708\u7684\u996e\u98df\u548c\u4f53\u91cd",
    "\u53ea\u770b\u8bad\u7ec3\u5907\u6ce8\uff0c\u4e0d\u770b\u6bcf\u65e5\u603b\u7ed3",
    "\u5206\u6790\u996e\u98df\u5b8f\u91cf\u548c\u5367\u63a8\u52a8\u4f5c\u8868\u73b0",
    "\u770b\u80a9\u90e8\u6574\u4f53\u8bad\u7ec3\uff0c\u4e0d\u5206\u6790\u5177\u4f53\u52a8\u4f5c",
    "\u8ffd\u6eaf\u6700\u8fd1\u4e00\u5468\u539f\u59cb\u8bb0\u5f55",
    "\u770b\u770b\u6700\u8fd1\u7684\u60c5\u51b5",
    "\u4e00\u6574\u4e2a\u6708\u7684\u4f53\u91cd\u8d70\u52bf",
    "\u770b\u770b\u63a8\u80f8\u6709\u6ca1\u6709\u8fdb\u6b65",
    "\u5220\u9664\u6700\u8fd1\u8bad\u7ec3\u8bb0\u5f55",
    "\u6211\u60f3\u77e5\u9053\u6700\u8fd1\u7684\u996e\u98df\u662f\u5426\u5f71\u54cd\u4e86\u8bad\u7ec3\u72b6\u6001\uff0c\u9700\u8981\u51c6\u5907\u54ea\u4e9b\u6570\u636e",
    "\u5e2e\u6211\u51c6\u5907\u4e00\u4efd\u53ef\u4ee5\u4ea4\u7ed9 GPT \u5206\u6790\u51cf\u8102\u72b6\u6001\u7684\u6570\u636e",
    "\u7ed3\u5408\u996e\u98df\u3001\u8bad\u7ec3\u548c\u4f53\u91cd\u5224\u65ad\u6211\u73b0\u5728\u5904\u4e8e\u4ec0\u4e48\u72b6\u6001",
]


def post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    with TemporaryDirectory(prefix="fitness-ledger-intelligent-export-web-") as name:
        root = Path(name)
        tracker, dictionary = fixture(root)
        before = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracker, dictionary))
        service = LedgerWebService(tracker, dictionary, root / "backups")
        server = create_server(port=0, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            results = [post(f"http://127.0.0.1:{server.server_port}/api/intelligent-export/preview", {"request": item}) for item in SCENARIOS]
            assert all(item.get("model_calls") == 0 for item in results)
            assert all(item.get("deterministic") is True for item in results)
            assert all(item.get("status") == "ready" for item in results[:5])
            assert all(item.get("status") != "ready" for item in results[5:9])
            assert all(item.get("status") == "ready" for item in results[9:])
            ready = results[0]
            assert ready["plan"]["selected_modules"]
            assert ready["output"]["markdown"] and ready["output"]["json"]
            html = urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/index.html", timeout=10).read().decode("utf-8")
            app_js = urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/app.js", timeout=10).read().decode("utf-8")
            assert "intelligent-export-request" in app_js
            assert "data-intelligent-review" in app_js
            assert "intelligent-export-candidate" in app_js
            assert "Analysis" in html or "Fitness Ledger" in html
        finally:
            server.shutdown()
            server.server_close()
        after = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (tracker, dictionary))
        assert before == after
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_WEB_OK")


if __name__ == "__main__":
    main()
