"""Guard the formal PWA bundle against candidate-only share-review traces."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PWA = ROOT / "mobile_viewer" / "pwa"


def main() -> None:
    required = ["share.html", "share.css", "share.js", "api.js", "manifest.webmanifest", "sw.js", "app.js"]
    missing = [name for name in required if not (PWA / name).is_file()]
    assert not missing, f"missing formal share files: {missing}"

    forbidden_files = ["share-review.html", "share-review.css", "share-review.js"]
    present = [name for name in forbidden_files if (PWA / name).exists()]
    assert not present, f"candidate files leaked into formal PWA: {present}"

    source = "\n".join((PWA / name).read_text(encoding="utf-8") for name in required)
    forbidden_tokens = [
        "模拟手机分享",
        "anonymous-review-fixture",
        "fitness-ledger:share-inbox:v1",
        "share_inbox.json",
        "CANDIDATE REVIEW",
    ]
    leaked = [token for token in forbidden_tokens if token in source]
    assert not leaked, f"candidate wording/state leaked into formal PWA: {leaked}"

    manifest = json.loads((PWA / "manifest.webmanifest").read_text(encoding="utf-8"))
    target = manifest.get("share_target") or {}
    assert target.get("action") == "./share.html"
    assert target.get("method") == "GET"
    assert target.get("params", {}).get("text") == "share_text"
    config = (PWA / "config.js").read_text(encoding="utf-8")
    assert "requireWebAuth: true" in config
    assert "cloud1-" in config

    share = (PWA / "share.js").read_text(encoding="utf-8")
    assert 'import { privateDatabase } from "./api.js";' in share
    assert '"fl_web_share_inbox"' in share
    assert '"{openid}"' in share
    assert "不会直接写入正式记录" in share
    for forbidden_collection in ("fl_daily_records", "fl_data_module_records", "fl_diet_records", "fl_training_sessions"):
        assert forbidden_collection not in share, f"share page must not write formal collection: {forbidden_collection}"

    api = (PWA / "api.js").read_text(encoding="utf-8")
    assert "export async function privateDatabase()" in api
    assert "getLoginState" in api

    service_worker = (PWA / "sw.js").read_text(encoding="utf-8")
    assert 'fitness-ledger-pwa-v25' in service_worker
    assert '"./share.html"' in service_worker
    assert '"./share.js"' in service_worker

    app = (PWA / "app.js").read_text(encoding="utf-8")
    assert 'register("./sw.js?v=20260816-01"' in app
    handoff_doc = (ROOT / "docs" / "maintenance" / "PWA_SHARE_INBOX_PHASE3.md").read_text(encoding="utf-8")
    assert 'Collection: `fl_web_share_inbox`' in handoff_doc
    assert "读取和修改本人数据 [PRIVATE]" in handoff_doc
    print("PWA_PRODUCTION_BUNDLE: PASS")


if __name__ == "__main__":
    main()
