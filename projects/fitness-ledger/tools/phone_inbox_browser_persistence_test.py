"""Browser-level candidate test for local-file inbox persistence and restart."""

from __future__ import annotations

import json
import subprocess
import tempfile
from typing import Any

from data_module_formal_mirror_browser_e2e_test import _close_process, _safe_cleanup, _start_browser, _start_service, _wait
from data_module_browser_e2e_test import _free_port


MOCK_CLOUDBASE = r"""
(() => {
  const rows = Array.from({length: 8}, (_, index) => ({
    _id: `FL_MOBILE_E2E_BROWSER_${String(index + 1).padStart(2, '0')}`,
    owner_uid: "web-user", client_id: `browser-client-${index + 1}`,
    title: `手机测试 ${index + 1}`, text: `FL_MOBILE_E2E_BROWSER_${String(index + 1).padStart(2, '0')} 中文\nEnglish，标点：，。`,
    source: "pwa_note", status: "pending", received_at: index + 1, updated_at: index + 1
  }));
  function matches(row, filter) { return Object.entries(filter || {}).every(([key, value]) => String(row[key] || '') === String(value || '')); }
  function query(filter = {}) { return { where(extra) { return query({ ...filter, ...extra }); }, orderBy() { return this; }, limit() { return this; }, async get() { return { data: rows.filter(row => matches(row, filter)) }; }, async update(payload) { rows.forEach(row => { if (matches(row, filter)) Object.assign(row, payload.data || payload || {}); }); return { updated: 1 }; } }; }
  const collection = { where(filter) { return query(filter); }, doc(id) { return { async update(payload) { Object.assign(rows.find(row => row._id === id) || {}, payload.data || payload || {}); } }; } };
  window.cloudbase = { init() { return { auth: () => ({ async getLoginState() { return { loginType: 'CUSTOM', isCustomAuth: true, user: { uid: 'web-user' } }; } }), database: () => ({ collection() { return collection; } }) }; } };
})()
"""


def open_inbox(browser: Any) -> dict[str, Any]:
    browser.evaluate(MOCK_CLOUDBASE)
    browser.evaluate("document.querySelector('[data-phone-daily-records]').click()")
    _wait(browser, "document.querySelectorAll('.phone-inbox-item').length === 7")
    return browser.evaluate("(async()=>{const local=await (await fetch('/api/phone-inbox/local',{cache:'no-store'})).json();return {count:document.querySelectorAll('.phone-inbox-item').length,text:document.body.innerText,local}})()")


def main() -> None:
    port = _free_port()
    service: subprocess.Popen[str] | None = None
    browser: Any = None
    edge: subprocess.Popen[bytes] | None = None
    edge_data: tempfile.TemporaryDirectory[str] | None = None
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-phone-inbox-browser-persistence-")
    try:
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "document.querySelector('#raw-entry') !== null")
        first = open_inbox(browser)
        assert first["local"]["status"] == "ready"
        assert len(first["local"]["items"]) == 7
        assert "FL_MOBILE_E2E_BROWSER_08" in first["text"]
        assert "FL_MOBILE_E2E_BROWSER_01" not in first["text"]
        browser.close(); browser = None
        _close_process(edge); edge = None
        _safe_cleanup(edge_data); edge_data = None
        _close_process(service); service = None
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "document.querySelector('#raw-entry') !== null")
        second = open_inbox(browser)
        assert len(second["local"]["items"]) == 7
        assert [item["_id"] for item in second["local"]["items"]] == [f"FL_MOBILE_E2E_BROWSER_{n:02d}" for n in range(8, 1, -1)]
        print(json.dumps({"status": "PASS", "cloud_rows": 8, "local_rows": 7, "after_restart_rows": 7, "latest_first": True, "oldest_local_evicted": True, "file_schema": second["local"]["schema_version"], "file_path": second["local"]["path"], "page_visible": True}, ensure_ascii=False))
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        _close_process(edge)
        _close_process(service)
        _safe_cleanup(edge_data)
        sandbox.cleanup()


if __name__ == "__main__":
    main()
