"""Browser acceptance test for the unified Daily Entry input board."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from data_module_formal_mirror_browser_e2e_test import (
    _click,
    _close_process,
    _safe_cleanup,
    _set_css,
    _start_browser,
    _start_service,
    _wait,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    port = None
    service: subprocess.Popen[str] | None = None
    edge: subprocess.Popen[bytes] | None = None
    browser: Any = None
    edge_data: tempfile.TemporaryDirectory[str] | None = None
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-unified-entry-browser-")
    try:
        from data_module_browser_e2e_test import _free_port

        port = _free_port()
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        _wait(browser, "!!document.querySelector('#entry-input-mode')")
        assert browser.evaluate("document.querySelectorAll('[data-natural-import]').length") == 0
        assert browser.evaluate("document.querySelectorAll('[data-phone-share-send]').length") == 0

        # The original formatted input and natural language both stay on the
        # same board; only the parser mode changes.
        browser.evaluate("document.querySelector('#entry-input-mode').value='standard'")
        _set_css(browser, "#raw-entry", "2099-01-01 体重 69 kg")
        _click(browser, "#parse")
        _wait(browser, "!!document.querySelector('.review-document')")
        assert not browser.evaluate("!!document.querySelector('.review-source-badge')")

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        browser.evaluate("document.querySelector('#entry-input-mode').value='natural'")
        _set_css(browser, "#raw-entry", "2099-01-02 体重 70 kg")
        before = browser.evaluate("(async()=>JSON.stringify(await (await fetch('/api/body')).json()))()")
        _click(browser, "#parse")
        _wait(browser, "!!document.querySelector('.review-source-badge')")
        assert browser.evaluate("document.querySelector('.review-source-badge').textContent") == "尚未保存"
        after_preview = browser.evaluate("(async()=>JSON.stringify(await (await fetch('/api/body')).json()))()")
        assert after_preview == before, (before, after_preview)

        _click(browser, "[data-review-save]")
        deadline = time.time() + 12
        after_save = ""
        while time.time() < deadline:
            after_save = browser.evaluate("(async()=>JSON.stringify(await (await fetch('/api/body')).json()))()")
            if "2099-01-02" in after_save:
                break
            time.sleep(0.1)
        assert "2099-01-02" in after_save, after_save
        print(json.dumps({
            "status": "PASS",
            "one_input_board": True,
            "standard_mode_preview": True,
            "natural_mode_preview": True,
            "preview_zero_write": before == after_preview,
            "confirm_saved_date": "2099-01-02",
            "standalone_natural_import_removed": True,
        }, ensure_ascii=False, indent=2))
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
