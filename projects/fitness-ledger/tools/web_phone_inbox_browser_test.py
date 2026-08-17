"""Browser acceptance test for the in-page desktop phone inbox."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from data_module_formal_mirror_browser_e2e_test import (
    _close_process,
    _safe_cleanup,
    _start_browser,
    _start_service,
    _wait,
    _command,
)
from data_module_browser_e2e_test import _free_port


MOCK_CLOUDBASE = r"""
(() => {
  const rows = [{ _id: "row-1", _openid: "web-user", title: "手机训练记录", text: "今天腰围 82.5 cm", status: "pending", received_at: Date.now() }];
  function matches(row, filter) { return Object.entries(filter || {}).every(([key, value]) => String(row[key] || '') === String(value || '').replace('{openid}', 'web-user').replace('{uid}', 'web-user')); }
  function query(filter = {}) { return { where(extra) { return query({ ...filter, ...extra }); }, orderBy() { return this; }, limit() { return this; }, async get() { return { data: rows.filter(row => matches(row, filter)) }; }, async update(payload) { rows.forEach(row => { if (matches(row, filter)) Object.assign(row, payload.data || {}); }); return { updated: 1 }; } }; }
  const collection = { where(filter) { return query(filter); }, doc(id) { return { async update(payload) { Object.assign(rows.find(row => row._id === id) || {}, payload.data || {}); }, async remove() {} }; } };
  window.cloudbase = { init() { return { auth: () => ({ async getLoginState() { return { loginType: 'CUSTOM', isCustomAuth: true, user: { uid: 'web-user' } }; } }), database: () => ({ collection() { return collection; } }) }; } };
})();
"""


def main() -> None:
    port = _free_port()
    service: subprocess.Popen[str] | None = None
    browser: Any = None
    edge: subprocess.Popen[bytes] | None = None
    edge_data: tempfile.TemporaryDirectory[str] | None = None
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-phone-inbox-browser-")
    try:
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools')")
        _wait(browser, "document.querySelector('[data-tools-panel=export]') !== null")
        assert browser.evaluate("document.querySelector('[data-phone-share-open]') === null") is True
        assert browser.evaluate("document.body.innerText.includes('ANALYSIS EXPORT')") is True

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "document.querySelector('#raw-entry') !== null")
        assert browser.evaluate("document.querySelector('#entry-input-mode') !== null && document.querySelector('[data-natural-import]') === null") is True
        browser.evaluate(MOCK_CLOUDBASE)
        browser.evaluate("document.querySelector('[data-phone-daily-records]').click()")
        _wait(browser, "document.querySelector('.phone-inbox-item') !== null")
        assert browser.evaluate("document.body.innerText.includes('今天腰围 82.5 cm')") is True
        assert browser.evaluate("document.querySelector('[data-phone-inbox-copy]') !== null") is True
        browser.evaluate("document.querySelector('[data-phone-inbox-use]').click()")
        _wait(browser, "document.querySelector('#raw-entry') !== null && document.querySelector('#raw-entry').value.includes('今天腰围 82.5 cm')")
        print(json.dumps({"status": "PASS", "tools_export_restored": True, "daily_entry_inbox_modal": True, "recent_item_visible": True, "copy_action_visible": True, "returned_to_original_input_board": True}, ensure_ascii=False))
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
