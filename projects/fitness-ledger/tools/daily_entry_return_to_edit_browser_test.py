"""Browser regression test for retaining Daily Entry raw text after Review."""

from __future__ import annotations

import json
import subprocess
import tempfile
from typing import Any

from data_module_formal_mirror_browser_e2e_test import _click, _close_process, _safe_cleanup, _set_css, _start_browser, _start_service, _wait
from data_module_browser_e2e_test import _free_port


def main() -> None:
    port = _free_port()
    service: subprocess.Popen[str] | None = None
    edge: subprocess.Popen[bytes] | None = None
    browser: Any = None
    edge_data: tempfile.TemporaryDirectory[str] | None = None
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-return-to-edit-")
    raw = "2099-01-01 体重 69 kg\n训练：背"
    try:
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        _set_css(browser, "#raw-entry", raw)
        _click(browser, "#parse")
        _wait(browser, "!!document.querySelector('.review-document')")
        _click(browser, "[data-review-back]")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        assert browser.evaluate("document.querySelector('#raw-entry').value") == raw
        print(json.dumps({"status": "PASS", "raw_text_retained_after_review_back": True}, ensure_ascii=False))
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
