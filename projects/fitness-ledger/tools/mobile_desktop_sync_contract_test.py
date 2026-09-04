"""Static contracts for the phone inbox and save-triggered sync handoff."""

from __future__ import annotations

from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
WEB_APP = PROJECT / "web_desktop" / "frontend" / "app.js"
WEB_SERVER = PROJECT / "web_desktop" / "backend" / "server.py"
PHONE_CLIENT = PROJECT / "web_desktop" / "frontend" / "phone-inbox-client.js"
PHONE_STORE = PROJECT / "web_desktop" / "backend" / "phone_inbox.py"
SHARE = PROJECT / "mobile_viewer" / "pwa" / "share.js"
PWA_APP = PROJECT / "mobile_viewer" / "pwa" / "app.js"


def main() -> None:
    app = WEB_APP.read_text(encoding="utf-8")
    server = WEB_SERVER.read_text(encoding="utf-8")
    phone_client = PHONE_CLIENT.read_text(encoding="utf-8")
    phone_store = PHONE_STORE.read_text(encoding="utf-8")
    share = SHARE.read_text(encoding="utf-8")
    pwa = PWA_APP.read_text(encoding="utf-8")

    for marker in (
        "data-phone-daily-records",
        "data-phone-inbox-use",
        "data-phone-inbox-processed",
        "loadPhoneInboxClient",
        "PHONE_INBOX_ACCOUNT_REQUIRED",
        "trigger:'auto_save'",
        "async function autoSyncAfterSave()",
        "payload_stale===true",
    ):
        assert marker in app, f"missing desktop sync marker: {marker}"

    assert "trigger = str(request.get(\"trigger\") or \"manual\")" in server
    assert '"trigger": trigger' in server
    assert "owner_uid" in phone_client and "listRecent" in phone_client and "updateStatus" in phone_client
    assert "RECENT_DAYS = 7" in phone_client and "QUERY_LIMIT = 50" in phone_client
    assert "KEEP_COUNT = 7" in phone_client and "slice(0, KEEP_COUNT)" in phone_client
    assert "云端只负责接收" in phone_client
    assert "Number(item.received_at || 0) >= cutoff" not in phone_client
    assert '"notes": item.notes' in server
    assert "state.movementHistory?.movement?.notes" in app
    assert "REQUEST_TIMEOUT_MS = 15000" in phone_client and "PHONE_INBOX_READ_TIMEOUT" in phone_client
    assert "/api/phone-inbox/local" in phone_client and "/api/phone-inbox/sync" in phone_client
    assert "PhoneInboxStore" in server and '"phone_inbox_local_persistence": True' in server
    assert "last_message_id" in phone_store and "os.replace" in phone_store
    assert "localStorage" not in phone_client
    assert 'phone-inbox-client.js?v=' in app
    assert "autoSyncOutcomeMessage" in app and "reconciled:true" in app
    assert "notice" in share and "已复制到剪贴板" in share
    assert "pendingSend" in share and "confirm-send" in share
    assert 'state.incoming.mode === "outbound"' in share
    assert "noteCopyStatus" in pwa and "copyNoteToClipboard" in pwa
    assert "share-send-confirm" in share and "再次确认发送" in share
    print("FITNESS_LEDGER_MOBILE_DESKTOP_SYNC_CONTRACT_OK")


if __name__ == "__main__":
    main()
