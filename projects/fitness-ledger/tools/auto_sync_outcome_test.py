"""Contract checks for truthful post-save Cloud Sync feedback."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
APP = PROJECT / "web_desktop" / "frontend" / "app.js"


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    start = source.index("function autoSyncOutcomeMessage")
    end = source.index("function updateSyncNav", start)
    helper = source[start:end]
    assert "autoSyncAfterSave()" in source
    assert "latestStatus.sync_status==='SYNCED'" in source
    assert "reconciled:true" in source
    assert "reconciled:!['SYNCED','NO_CHANGES'].includes(result.status)" in source
    assert "const headerHint=main.querySelector('.admin-page-header p')" in source
    assert "headerHint.textContent=syncHint" in source

    script = f"""
{helper}
const output = [
  autoSyncOutcomeMessage({{ status: 'SYNCED' }}),
  autoSyncOutcomeMessage({{ status: 'SYNCED', reconciled: true }}),
  autoSyncOutcomeMessage({{ status: 'UPLOAD_FAILED' }}),
  autoSyncOutcomeMessage({{ status: 'UNKNOWN' }}),
  autoSyncOutcomeMessage({{ status: 'AUTO_SYNC_DISABLED' }})
];
console.log(JSON.stringify(output));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    messages = json.loads(completed.stdout)
    assert "已自动同步到云端" in messages[0]
    assert "已复核为成功" in messages[1]
    assert "未完成（UPLOAD_FAILED）" in messages[2]
    assert "暂无法确认" in messages[3]
    assert "未启用" in messages[4]
    print("FITNESS_LEDGER_AUTO_SYNC_OUTCOME_OK")


if __name__ == "__main__":
    main()
