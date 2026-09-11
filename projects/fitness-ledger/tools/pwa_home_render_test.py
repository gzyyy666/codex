"""Phone-size smoke for homepage module stability across async reads."""

from __future__ import annotations

import json
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


def command(browser: DevToolsSocket, method: str, params: dict | None = None):
    command_id = browser.next_id
    browser.next_id += 1
    browser._send_frame(json.dumps({"id": command_id, "method": method, "params": params or {}}).encode("utf-8"))
    while True:
        opcode, payload = browser._receive_frame()
        if opcode == 9:
            browser._send_frame(payload, opcode=10)
            continue
        if opcode == 8:
            raise RuntimeError("browser websocket closed")
        if opcode != 1:
            continue
        decoded = json.loads(payload.decode("utf-8"))
        if decoded.get("id") == command_id:
            if "error" in decoded:
                raise AssertionError(decoded["error"])
            return decoded.get("result")


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
        command(browser, "Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True,
            "screenWidth": 390, "screenHeight": 844,
        })
        command(browser, "Page.reload", {"ignoreCache": True})
        wait_for(browser, "document.querySelectorAll('.home-module-pill').length >= 6")
        first = evaluate(browser, "document.querySelectorAll('.home-module-pill').length")
        stable = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(document.querySelectorAll('.home-module-pill').length), 800))")
        assert first == stable == 6, {"first": first, "stable": stable}
        assert evaluate(browser, "document.querySelector('[data-part-id=core]').className.includes('color-white')") is True
        evaluate(browser, "document.querySelector('.home-module-pill').click()")
        wait_for(browser, "!!document.querySelector('.movement-preview')")
        overview = evaluate(browser, "(() => { const card=document.querySelector('.movement-summary').getBoundingClientRect(); const nav=document.querySelector('.tabbar').getBoundingClientRect(); return {cardBottom:card.bottom, navTop:nav.top, viewport:innerHeight}; })()")
        assert overview["cardBottom"] <= overview["navTop"] + 1, overview
        selected_tone = evaluate(browser, "document.querySelector('.reference-home').className")
        assert any(name in selected_tone for name in ("theme-color-amber", "theme-color-ember", "theme-color-teal", "theme-color-violet", "theme-color-blue", "theme-color-rose")), selected_tone
        evaluate(browser, "document.querySelector('[data-action=toggle-archive]').click()")
        wait_for(browser, "document.querySelector('[data-home-state]').dataset.homeState === 'selected-expanded' && !!document.querySelector('.theme-archive-head')")
        assert evaluate(browser, "getComputedStyle(document.querySelector('.note-stack')).position") == "sticky"
        assert evaluate(browser, "getComputedStyle(document.querySelector('.theme-archive-head')).position") == "sticky"
        wait_for(browser, "getComputedStyle(document.querySelector('.home-shell')).getPropertyValue('--expanded-note-height').trim() !== ''")
        sticky_layout = evaluate(browser, "(() => { const home=document.querySelector('.home-shell'); return {note:Number.parseFloat(getComputedStyle(home).getPropertyValue('--expanded-note-height')), strip:Number.parseFloat(getComputedStyle(home).getPropertyValue('--expanded-strip-height'))}; })()")
        assert sticky_layout["note"] > 0 and sticky_layout["strip"] > 0, sticky_layout
        evaluate(browser, "document.querySelector('.theme-archive-list').style.minHeight='1200px'")
        before_scroll = evaluate(browser, "(() => { const note=document.querySelector('.note-sheet').getBoundingClientRect(); const list=document.querySelector('.theme-archive-list').getBoundingClientRect(); const card=document.querySelector('.movement-card')?.getBoundingClientRect(); return {noteTop:note.top, listTop:list.top, cardTop:card?.top ?? null}; })()")
        evaluate(browser, "window.scrollTo(0, document.querySelector('.theme-archive-head').offsetTop + 180)")
        after_scroll = evaluate(browser, "new Promise(resolve => setTimeout(() => { const note=document.querySelector('.note-sheet').getBoundingClientRect(); const stack=document.querySelector('.note-stack').getBoundingClientRect(); const strip=document.querySelector('.theme-strip').getBoundingClientRect(); const head=document.querySelector('.theme-archive-head').getBoundingClientRect(); const list=document.querySelector('.theme-archive-list').getBoundingClientRect(); const card=document.querySelector('.movement-card')?.getBoundingClientRect(); const home=document.querySelector('.home-shell'); resolve({noteTop:note.top, stackTop:stack.top, stripTop:strip.top, headTop:head.top, listTop:list.top, cardTop:card?.top ?? null, scrollY:scrollY, position:getComputedStyle(document.querySelector('.note-stack')).position, homeHeight:home.getBoundingClientRect().height, homeOverflow:getComputedStyle(home).overflow, pageOverflow:getComputedStyle(document.querySelector('.reference-home')).overflow, bodyOverflow:getComputedStyle(document.body).overflow}); }, 80))")
        assert after_scroll["noteTop"] <= 2, after_scroll
        assert after_scroll["stripTop"] >= after_scroll["noteTop"] + sticky_layout["note"] - 3, after_scroll
        assert after_scroll["headTop"] >= after_scroll["stripTop"] + sticky_layout["strip"] - 3, after_scroll
        moving_before = before_scroll["cardTop"] if before_scroll["cardTop"] is not None else before_scroll["listTop"]
        moving_after = after_scroll["cardTop"] if after_scroll["cardTop"] is not None else after_scroll["listTop"]
        assert moving_after != moving_before, {"before": before_scroll, "after": after_scroll}
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
