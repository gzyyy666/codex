"""Browser acceptance test for the desktop natural-language import flow."""

from __future__ import annotations

import json
import subprocess
import sys
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
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-natural-import-browser-")
    try:
        from data_module_browser_e2e_test import _free_port

        port = _free_port()
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        _wait(browser, "!!document.querySelector('[data-natural-import]')")
        _set_css(browser, "#raw-entry", "2099-01-01 体重 69 kg")
        _click(browser, "#parse")
        _wait(browser, "!!document.querySelector('.review-document')")
        assert not browser.evaluate("!!document.querySelector('.review-source-badge')")
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        _wait(browser, "!!document.querySelector('[data-natural-import]')")

        before = browser.evaluate(
            "(async()=>JSON.stringify(await (await fetch('/api/body')).json()))()"
        )
        _click(browser, "[data-natural-import]")
        _wait(browser, "!!document.querySelector('#natural-import-text')")
        _set_css(browser, "#natural-import-text", "2099-01-02 体重 70 kg")
        _click(browser, "[data-natural-import-confirm]")
        _wait(browser, "!!document.querySelector('.review-source-badge')")
        assert browser.evaluate("document.querySelector('.review-source-badge').textContent") == "尚未保存"
        after_preview = browser.evaluate(
            "(async()=>JSON.stringify(await (await fetch('/api/body')).json()))()"
        )
        assert after_preview == before, (before, after_preview)

        _click(browser, "[data-review-save]")
        deadline = time.time() + 12
        after_save = ""
        while time.time() < deadline:
            after_save = browser.evaluate(
                "(async()=>JSON.stringify(await (await fetch('/api/body')).json()))()"
            )
            if "2099-01-02" in after_save:
                break
            time.sleep(0.1)
        assert "2099-01-02" in after_save, after_save

        # An unknown metric still follows the same entry button, but opens the
        # existing Data Module definition preview instead of silently writing.
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        assert browser.evaluate("document.querySelectorAll('[data-natural-import]').length") == 1
        _click(browser, "[data-natural-import]")
        _wait(browser, "!!document.querySelector('#natural-import-text')")
        _set_css(browser, "#natural-import-text", "2099-01-03 晨间脉搏 58 bpm")
        _click(browser, "[data-natural-import-confirm]")
        _wait(browser, "!!document.querySelector('[data-dm-submit-definition]')")
        assert browser.evaluate("document.querySelector('[name=label]').value") == "晨间脉搏"
        print(json.dumps({
            "status": "PASS",
            "entry_button": True,
            "preview_zero_write": before == after_preview,
            "review_badge": True,
            "confirm_saved_date": "2099-01-02",
            "new_module_candidate_preview": True,
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
