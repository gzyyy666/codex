"""Static contract checks for the read-only mobile workbench PWA."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PWA = ROOT / "mobile_viewer" / "pwa"


def main() -> None:
    required = [
        PWA / "index.html",
        PWA / "manifest.webmanifest",
        PWA / "app.js",
        PWA / "data-modules.js",
        PWA / "api.js",
        PWA / "styles.css",
        PWA / "sw.js",
        PWA / "icons" / "fitness-ledger.png",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise AssertionError(f"missing PWA files: {missing}")

    manifest = json.loads((PWA / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    assert manifest["scope"] == "./"
    assert manifest["icons"]

    source = "\n".join(path.read_text(encoding="utf-8") for path in required if path.suffix in {".html", ".js", ".css"})
    app_source = (PWA / "app.js").read_text(encoding="utf-8")
    css_source = (PWA / "styles.css").read_text(encoding="utf-8")
    api_source = (PWA / "api.js").read_text(encoding="utf-8")
    for route in ("reference", "training", "status", "body", "diet", "record", "movement"):
        assert f'"{route}"' in app_source, f"missing Mini Program route: {route}"
    assert "NOTE_KEY" in app_source
    assert "toneForArea" in app_source
    assert 'freeform-notepad:v2:current-training' in app_source
    assert "findLastCandidate" in app_source
    assert "previewHistory" in app_source
    assert "renderCandidateSet" in app_source
    assert "previewSetParts" in app_source
    assert 'call("movementHistory"' in app_source
    assert "compositionstart" in app_source and "compositionend" in app_source
    assert "refreshCandidateOverlay" in app_source
    assert "noteHistoryCache" in app_source
    for marker in ("shareDraft", "sendTrainingNote", "share-confirm-primary", "PHONE_INBOX_LIMIT", "privateDatabase", "确认并发送"):
        assert marker in app_source, f"missing in-app phone handoff marker: {marker}"
    assert "prunePhoneInboxItems" not in app_source, "retention cleanup must run in CloudBase, not the phone"
    assert 'data-candidate-region' in app_source
    assert 'PWA v1.1.0' in app_source
    for marker in (
        'call("dataModules")',
        "mergeRecordsWithCategoryDates",
        "enhanceCategoryArchive",
        "enhanceRecordDetail",
        "renderPageWidgets",
        "route-back",
        "手机扩展指标",
    ):
        assert marker in source, f"missing phone Data Module marker: {marker}"
    candidate_update = app_source.split("async function updateCandidates()", 1)[1].split("async function openNoteCandidate", 1)[0]
    assert "render()" not in candidate_update, "candidate recognition must not redraw the whole page"
    assert 'autocomplete="off"' in app_source and 'autocorrect="off"' in app_source
    for marker in ("renderLogin", "signIn", "AUTH_REQUIRED", "Authorization", "cloudbase-js-sdk/2.27.1"):
        assert marker in source, f"missing Web authentication contract: {marker}"
    assert '.auth()' in api_source, "Web login must use the verified CloudBase auth initialization"
    assert "resetViewport" in app_source and "window.scrollTo(0, 0)" in app_source
    assert ".auth-card input { font-size: 16px; }" in css_source, "iOS login input must not trigger page zoom"
    for marker in ("renderNoteDock", "candidate-overlay", "candidate-edge-dot", "可能相关动作 · 最近记录", "previewSetLine", "note-detail-backdrop", "data-note-surface", "scheduleDockCheck"):
        assert marker in source, f"missing sealed Mini Program parity marker: {marker}"
    for marker in (
        ".reference-page .candidate-overlay { position: fixed; z-index: 55;",
        "width: min(542px, calc(100vw - 18px))",
        ".reference-page .notepad-dock { position: fixed; z-index: 40;",
        "width: min(538px, calc(100vw - 22px))",
        ".reference-page .note-detail-sheet { width: 100%; max-width: 560px;",
    ):
        assert marker in css_source, f"missing responsive overlay contract: {marker}"
    assert "home-page" not in app_source and "plan-grid" not in app_source
    forbidden = ["wx.cloud", "AppSecret", "FITNESS_LEDGER_ALLOWED_OPENIDS", "POST", "PUT", "DELETE"]
    violations = [token for token in forbidden if token in source]
    if violations:
        raise AssertionError(f"PWA must stay read-only and credential-free: {violations}")

    service_worker = (PWA / "sw.js").read_text(encoding="utf-8")
    assert 'includes("/api/")' in service_worker
    assert 'fitness-ledger-pwa-v29' in service_worker
    assert '"./data-modules.js"' in service_worker
    assert 'register("./sw.js?v=20260816-05", { updateViaCache: "none" })' in app_source
    desktop_icon = ROOT / "assets" / "fitness-ledger-monogram-v3.png"
    pwa_icon = PWA / "icons" / "fitness-ledger.png"
    assert hashlib.sha256(desktop_icon.read_bytes()).digest() == hashlib.sha256(pwa_icon.read_bytes()).digest()
    print("PWA static contract: PASS")


if __name__ == "__main__":
    main()
