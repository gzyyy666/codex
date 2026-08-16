"""Static contracts for the in-app phone handoff and save-triggered sync."""

from __future__ import annotations

from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
WEB_APP = PROJECT / "web_desktop" / "frontend" / "app.js"
WEB_CLIENT = PROJECT / "web_desktop" / "frontend" / "phone-inbox-client.js"
WEB_SERVER = PROJECT / "web_desktop" / "backend" / "server.py"
PWA_APP = PROJECT / "mobile_viewer" / "pwa" / "app.js"
MANIFEST = PROJECT / "mobile_viewer" / "pwa" / "manifest.webmanifest"
LEGACY_SHARE = PROJECT / "mobile_viewer" / "pwa" / "share.html"


def main() -> None:
    app = WEB_APP.read_text(encoding="utf-8")
    client = WEB_CLIENT.read_text(encoding="utf-8")
    server = WEB_SERVER.read_text(encoding="utf-8")
    pwa = PWA_APP.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")
    legacy_share = LEGACY_SHARE.read_text(encoding="utf-8")

    for marker in (
        "data-phone-daily-records",
        "renderPhoneInboxModal",
        "data-phone-inbox-login",
        "data-phone-inbox-use",
        "phone-inbox-client.js",
        "entry-input-mode",
        "data-dm-llm-template",
        "async function autoSyncAfterSave()",
        "payload_stale===true",
    ):
        assert marker in app, f"missing desktop handoff marker: {marker}"

    for forbidden in ("PHONE_SHARE_URL", "data-phone-share-open", "data-phone-share-send", "window.open(buildPhoneShareUrl"):
        assert forbidden not in app, f"desktop must not expose old outbound phone flow: {forbidden}"

    for marker in ("fl_web_share_inbox", "MAX_ITEMS", "export async function listRecent", "export async function prune", "{openid}"):
        assert marker in client, f"missing private inbox client marker: {marker}"
    assert 'trigger = str(request.get("trigger") or "manual")' in server
    assert '"trigger": trigger' in server

    for marker in ("shareDraft", "shareOpen", "sendTrainingNote", "PHONE_INBOX_LIMIT", "share-confirm-primary", "privateDatabase", "确认发送", "loadIncomingShareIntent"):
        assert marker in pwa, f"missing PWA handoff marker: {marker}"
    assert "share_target" in manifest and '"action": "./index.html"' in manifest
    assert "window.location.replace" in legacy_share
    assert "noteCopyStatus" in pwa and "copyNoteToClipboard" in pwa
    print("FITNESS_LEDGER_MOBILE_DESKTOP_SYNC_CONTRACT_OK")


if __name__ == "__main__":
    main()
