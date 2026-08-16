"""Static contract for the CloudBase-side share inbox retention job."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
FUNCTION = PROJECT / "cloudfunctions" / "fl_web_share_inbox_cleanup" / "index.js"
CONFIG = PROJECT / "cloudbaserc.share-inbox.example.json"


def main() -> None:
    source = FUNCTION.read_text(encoding="utf-8")
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert '"fl_web_share_inbox"' in source
    assert "KEEP_PER_OWNER = 7" in source
    assert "_openid" in source
    assert "received_at" in source
    assert "KEEP_PER_OWNER" in source
    assert "readAllRows" in source
    assert "orphanIds" in source
    assert ".remove()" in source
    assert "process.env.TCB_ENV" in source
    function = next(item for item in config["functions"] if item["name"] == "fl_web_share_inbox_cleanup")
    trigger = function["triggers"][0]
    assert trigger == {
        "name": "daily-share-inbox-cleanup",
        "type": "timer",
        "config": "0 0 3 * * * *",
    }
    assert config["envId"].startswith("cloud1-")
    print("CLOUD_SHARE_INBOX_CLEANUP_CONTRACT_OK")


if __name__ == "__main__":
    main()
