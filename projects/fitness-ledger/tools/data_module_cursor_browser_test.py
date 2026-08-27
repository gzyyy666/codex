"""Regression: the data-module editor keeps the trophy cursor and editable text caret."""

from __future__ import annotations

import tempfile

from data_module_formal_mirror_browser_e2e_test import (
    _click,
    _free_port,
    _start_browser,
    _start_service,
    _wait,
)


def main() -> None:
    port = _free_port()
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-cursor-sandbox-")
    service = edge = browser = edge_data = None
    try:
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools')")
        _wait(browser, "!!document.querySelector('.dm-sidebar-entry')")
        _click(browser, ".dm-sidebar-entry")
        _wait(browser, "!!document.querySelector('.dm-management-page')")

        # Reproduce the guardian's cursor mode immediately before opening the editor.
        browser.evaluate("document.documentElement.dataset.petCursor='trophy'; true")
        management = browser.evaluate("""(() => ({
            cursor: getComputedStyle(document.querySelector('.dm-management-page')).cursor,
            trophy_visible: getComputedStyle(document.querySelector('.tools-pet-cursor-trail')).opacity !== '0',
            trophy_passive: getComputedStyle(document.querySelector('.tools-pet-cursor-trail')).pointerEvents === 'none',
        }))()""")
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        result = browser.evaluate("""(() => {
            const input = document.querySelector('[name=label]');
            const modal = document.querySelector('.dm-modal');
            input.focus();
            return {
              input_cursor: getComputedStyle(input).cursor,
              caret_color: getComputedStyle(input).caretColor,
              modal_cursor: getComputedStyle(modal).cursor,
              focused: document.activeElement === input,
              trophy_visible: getComputedStyle(document.querySelector('.tools-pet-cursor-trail')).opacity !== '0',
              trophy_passive: getComputedStyle(document.querySelector('.tools-pet-cursor-trail')).pointerEvents === 'none',
              pet_hidden: [...document.querySelectorAll('.tools-pet-floating,.tools-pet-navigator')]
                .every(node => getComputedStyle(node).opacity === '0'),
            };
        })()""")
        result.update({f"management_{key}": value for key, value in management.items()})
        assert result["input_cursor"] == "text", result
        assert result["management_cursor"] == "none", result
        assert result["management_trophy_visible"], result
        assert result["management_trophy_passive"], result
        assert result["caret_color"] != "transparent", result
        assert result["modal_cursor"] == "none", result
        assert result["trophy_visible"] and result["trophy_passive"], result
        assert result["focused"], result
        assert result["pet_hidden"], result
        print({"status": "PASS", **result})
    finally:
        if browser is not None:
            browser.close()
        for process in (edge, service):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        if edge_data is not None:
            edge_data.cleanup()
        sandbox.cleanup()


if __name__ == "__main__":
    main()
