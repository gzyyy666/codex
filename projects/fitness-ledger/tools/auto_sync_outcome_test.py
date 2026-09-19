"""Contract checks for quiet post-save Cloud Sync feedback."""

from __future__ import annotations

from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
APP = PROJECT / "web_desktop" / "frontend" / "app.js"


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    assert "autoSyncAfterSave()" in source
    assert "previousSyncWasConfirmed" in source
    assert "showToast('上次云同步已确认。')" in source
    assert "const previousSyncCheck=api('/api/cloud-sync/status').catch(()=>null);" in source
    assert "void autoSyncAfterSave();" in source
    assert "CLOUD_SYNC_TIMEOUT_MS=60000" in source
    assert "for(let attempt=0;attempt<4;attempt++)" not in source
    assert "自动同步结果暂无法确认" not in source
    assert "showAutoSyncReceipt" not in source
    assert "autoSyncOutcomeMessage" not in source
    assert "const headerHint=main.querySelector('.admin-page-header p')" in source
    assert "headerHint.textContent=syncHint" in source
    assert source.index("const previousSyncCheck=") < source.index("postApi(naturalLanguageReview?")
    print("FITNESS_LEDGER_AUTO_SYNC_FEEDBACK_OK")


if __name__ == "__main__":
    main()
