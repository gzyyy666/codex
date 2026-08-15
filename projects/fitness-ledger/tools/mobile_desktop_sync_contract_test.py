"""Static contracts for the phone inbox and save-triggered sync handoff."""

from __future__ import annotations

from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
WEB_APP = PROJECT / "web_desktop" / "frontend" / "app.js"
WEB_SERVER = PROJECT / "web_desktop" / "backend" / "server.py"
SHARE = PROJECT / "mobile_viewer" / "pwa" / "share.js"
PWA_APP = PROJECT / "mobile_viewer" / "pwa" / "app.js"


def main() -> None:
    app = WEB_APP.read_text(encoding="utf-8")
    server = WEB_SERVER.read_text(encoding="utf-8")
    share = SHARE.read_text(encoding="utf-8")
    pwa = PWA_APP.read_text(encoding="utf-8")

    for marker in (
        "PHONE_SHARE_URL",
        "data-phone-share-open",
        "data-phone-share-send",
        "window.confirm('确认把当前记事板内容发送到云端收件箱？这不会直接写入正式记录。')",
        "share_mode",
        "trigger:'auto_save'",
        "async function autoSyncAfterSave()",
        "payload_stale===true",
    ):
        assert marker in app, f"missing desktop sync marker: {marker}"

    assert "trigger = str(request.get(\"trigger\") or \"manual\")" in server
    assert '"trigger": trigger' in server
    assert "notice" in share and "已复制到剪贴板" in share
    assert 'state.incoming.mode === "outbound"' in share
    assert "noteCopyStatus" in pwa and "copyNoteToClipboard" in pwa
    print("FITNESS_LEDGER_MOBILE_DESKTOP_SYNC_CONTRACT_OK")


if __name__ == "__main__":
    main()
