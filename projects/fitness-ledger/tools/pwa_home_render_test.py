"""Phone-size smoke for homepage module stability across async reads."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from pathlib import Path

from data_module_browser_e2e_test import DevToolsSocket, _edge_path, _free_port, _wait_target, _wait_http


PROJECT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT / "tools" / "run_data_module_pwa_review.py"


def evaluate(browser: DevToolsSocket, expression: str):
    return browser.evaluate(expression)


def wait_for(browser: DevToolsSocket, expression: str, timeout: float = 12):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if evaluate(browser, expression):
            return
        time.sleep(0.1)
    raise AssertionError(f"browser condition timed out: {expression}")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    port, debug_port = _free_port(), _free_port()
    service = None
    edge = None
    browser = None
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-home-edge-")
    try:
        service = subprocess.Popen(
            [sys.executable, "-u", str(LAUNCHER), "--port", str(port)],
            cwd=PROJECT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        edge = subprocess.Popen(
            [str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run",
             "--no-default-browser-check", f"--remote-debugging-port={debug_port}",
             f"--user-data-dir={profile.name}", f"http://127.0.0.1:{port}/pwa/#reference"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        target = _wait_target(debug_port, f"http://127.0.0.1:{port}/pwa/")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        wait_for(browser, "document.querySelectorAll('.home-module-pill').length >= 6")
        first = evaluate(browser, "document.querySelectorAll('.home-module-pill').length")
        stable = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(document.querySelectorAll('.home-module-pill').length), 800))")
        assert first == stable == 6, {"first": first, "stable": stable}
        evaluate(browser, "document.querySelector('.home-module-pill').click()")
        wait_for(browser, "!!document.querySelector('.movement-preview')")
        selected_tone = evaluate(browser, "document.querySelector('.reference-home').className")
        assert any(name in selected_tone for name in ("theme-color-amber", "theme-color-ember", "theme-color-teal", "theme-color-violet", "theme-color-blue", "theme-color-rose")), selected_tone
        evaluate(browser, "document.querySelector('[data-action=toggle-archive]').click()")
        wait_for(browser, "document.querySelector('[data-home-state]').dataset.homeState === 'selected-expanded'")
        assert evaluate(browser, "getComputedStyle(document.querySelector('.note-stack')).position") == "sticky"
        first_module = evaluate(browser, "document.querySelector('[data-part-id]').dataset.partId")
        evaluate(browser, "document.querySelectorAll('.home-module-pill')[1].click()")
        wait_for(browser, "document.querySelector('[data-home-state]').dataset.homeState === 'selected-expanded' && document.querySelector('[data-part-id].is-active').dataset.partId !== arguments[0]".replace("arguments[0]", repr(first_module)))
        assert evaluate(browser, "document.querySelector('[data-home-state]').dataset.homeState") == "selected-expanded"
        evaluate(browser, "document.querySelector('[data-note]').focus()")
        focused = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(document.querySelectorAll('.home-module-pill').length), 500))")
        assert focused == 6, focused
        print("PWA_HOME_RENDER_STABILITY: PASS")
    finally:
        if browser is not None:
            browser.close()
        stop(edge)
        stop(service)
        profile.cleanup()


if __name__ == "__main__":
    main()
