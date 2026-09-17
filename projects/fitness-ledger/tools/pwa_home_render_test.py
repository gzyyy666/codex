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
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-home-edge-", ignore_cleanup_errors=True)
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
        initial = evaluate(browser, "({ pills: document.querySelectorAll('.home-module-pill').length, loading: !!document.querySelector('.theme-strip--loading') })")
        assert initial["pills"] == 0, initial
        wait_for(browser, "document.querySelectorAll('.home-module-pill').length >= 6")
        first = evaluate(browser, "document.querySelectorAll('.home-module-pill').length")
        stable = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(document.querySelectorAll('.home-module-pill').length), 800))")
        order = evaluate(browser, "Array.from(document.querySelectorAll('.home-module-pill'), item => item.dataset.partId)")
        assert first == stable == 8, {"first": first, "stable": stable, "order": order}
        assert order == ["chest", "shoulders", "back", "legs", "glutes", "arms", "core", "cardio"], order
        assert evaluate(browser, "document.querySelector('[data-part-id=core]').className.includes('color-white')") is True
        evaluate(browser, "document.querySelector('.home-module-pill:nth-child(6)').click()")
        wait_for(browser, "document.querySelector('[data-home-state]')?.dataset.homeState === 'selected-expanded' && !!document.querySelector('.theme-archive')")
        wait_for(browser, "document.querySelectorAll('.movement-card').length > 0")
        selected = evaluate(browser, "({state:document.querySelector('[data-home-state]').dataset.homeState, preview:!!document.querySelector('.movement-preview'), collapse:!!document.querySelector('.archive-collapse'), cards:document.querySelectorAll('.movement-card').length})")
        assert selected["state"] == "selected-expanded" and not selected["preview"] and not selected["collapse"] and selected["cards"] > 0, selected
        selected_note_height = evaluate(browser, "document.querySelector('.note-sheet').getBoundingClientRect().height")
        assert 250 <= selected_note_height <= 270, selected_note_height
        selected_geometry = evaluate(browser, "(() => { const pill=document.querySelector('.home-module-pill'); const card=document.querySelector('.movement-card'); const tab=document.querySelector('.tabbar'); return {pillHeight:pill.getBoundingClientRect().height, cardBottom:card.getBoundingClientRect().bottom, usableBottom:innerHeight-(tab?.getBoundingClientRect().height || 0)}; })()")
        assert 36 <= selected_geometry["pillHeight"] <= 40, selected_geometry
        assert selected_geometry["cardBottom"] <= selected_geometry["usableBottom"] + 2, selected_geometry
        evaluate(browser, "document.querySelector('.home-shell').insertAdjacentHTML('beforeend', '<div data-test-page-spacer style=\"height:1600px\"></div>'); window.scrollTo(0, 360); true")
        pre_focus_layout = evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.value=Array.from({length:24}, (_, i) => `普通记录${i + 1}`).join('\\n'); note.setSelectionRange(note.value.length, note.value.length); note.dispatchEvent(new Event('input', {bubbles:true})); const sheet=document.querySelector('.note-sheet').getBoundingClientRect(); const style=getComputedStyle(note); return {pageY:scrollY, sheetHeight:sheet.height, fontSize:style.fontSize, lineHeight:style.lineHeight}; })()")
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true})); note.focus(); return true; })()")
        command(browser, "Emulation.setDeviceMetricsOverride", {"width": 390, "height": 500, "deviceScaleFactor": 1, "mobile": True, "screenWidth": 390, "screenHeight": 844})
        wait_for(browser, "document.documentElement.classList.contains('pwa-keyboard-open')")
        evaluate(browser, "new Promise(resolve => setTimeout(resolve, 650))")
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.scrollTop=0; note.dispatchEvent(new Event('select',{bubbles:true})); return true; })()")
        evaluate(browser, "new Promise(resolve => setTimeout(resolve, 650))")
        focus_state = evaluate(browser, "(() => { const e=document.querySelector('[data-note]'); const s=getComputedStyle(e); const vv=visualViewport; const line=Number.parseFloat(s.lineHeight); const top=e.getBoundingClientRect().top+Number.parseFloat(s.borderTopWidth)+Number.parseFloat(s.paddingTop)+(e.value.slice(0,e.selectionStart).split('\\n').length-1)*line-e.scrollTop; const probe=document.createElement('div'); probe.style.cssText='position:absolute;visibility:hidden;width:2.5cm;height:0'; document.body.append(probe); const clearance=probe.getBoundingClientRect().width; probe.remove(); const sheet=document.querySelector('.note-sheet').getBoundingClientRect(); return {focused:document.documentElement.classList.contains('pwa-note-focused'), locked:document.documentElement.classList.contains('pwa-note-scroll-locked'), overflow:getComputedStyle(document.documentElement).overflow, top, target:vv.offsetTop+clearance, pageY:scrollY, sheetHeight:sheet.height, fontSize:s.fontSize, lineHeight:s.lineHeight, scrollTop:e.scrollTop, maxScroll:e.scrollHeight-e.clientHeight}; })()")
        assert focus_state["focused"] and focus_state["locked"] and focus_state["overflow"] == "hidden", focus_state
        # The target is a lower bound: a line already above it must not be
        # pushed down just to reach the marker.
        assert abs(focus_state["top"] - focus_state["target"]) <= 14, focus_state
        assert focus_state["scrollTop"] > 0 and focus_state["maxScroll"] >= focus_state["scrollTop"], focus_state
        assert abs(focus_state["pageY"] - pre_focus_layout["pageY"]) <= 1, {"before": pre_focus_layout, "after": focus_state}
        assert abs(focus_state["sheetHeight"] - pre_focus_layout["sheetHeight"]) <= 1, {"before": pre_focus_layout, "after": focus_state}
        assert focus_state["fontSize"] == pre_focus_layout["fontSize"] and focus_state["lineHeight"] == pre_focus_layout["lineHeight"], {"before": pre_focus_layout, "after": focus_state}
        locked_y = evaluate(browser, "scrollY")
        evaluate(browser, "window.scrollTo(0, scrollY + 500); true")
        settled_y = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(scrollY), 120))")
        assert abs(settled_y - locked_y) <= 1, {"before": locked_y, "after": settled_y}
        editor_scroll = evaluate(browser, "(() => { const e=document.querySelector('[data-note]'); e.scrollTop=e.scrollHeight; return {scrollTop:e.scrollTop, page:scrollY}; })()")
        assert editor_scroll["scrollTop"] > 0 and abs(editor_scroll["page"] - locked_y) <= 1, editor_scroll
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.value='器械三头下压'; note.setSelectionRange(note.value.length, note.value.length); note.dispatchEvent(new Event('input', {bubbles:true})); return true; })()")
        wait_for(browser, "!!document.querySelector('.candidate-overlay .candidate b')")
        candidate_layout = evaluate(browser, "(() => { const candidate=document.querySelector('.candidate-overlay'); const note=document.querySelector('.note-sheet').getBoundingClientRect(); const editor=document.querySelector('[data-note]'); const s=getComputedStyle(editor); const caretBottom=editor.getBoundingClientRect().top+Number.parseFloat(s.borderTopWidth)+Number.parseFloat(s.paddingTop)+Number.parseFloat(s.lineHeight)-editor.scrollTop; return {display:getComputedStyle(candidate).display, name:document.querySelector('.candidate b').textContent, width:candidate.getBoundingClientRect().width, sheetWidth:note.width, gap:candidate.getBoundingClientRect().top-caretBottom-Number.parseFloat(s.lineHeight)}; })()")
        assert candidate_layout["display"] != "none" and candidate_layout["name"] == "器械三头下压", candidate_layout
        assert abs(candidate_layout["width"] - candidate_layout["sheetWidth"]) <= 2 and abs(candidate_layout["gap"]) <= 5, candidate_layout
        evaluate(browser, "(() => { const list=document.querySelector('.candidate-history-list'); const first=list.querySelector('.candidate-history'); list.append(first.cloneNode(true),first.cloneNode(true)); const scroll=document.querySelector('.candidate-scroll'); scroll.style.setProperty('--candidate-latest-height', `${Math.ceil(first.getBoundingClientRect().height + 8)}px`); return true; })()")
        wait_for(browser, "document.querySelector('.candidate-scroll').scrollHeight > document.querySelector('.candidate-scroll').clientHeight")
        nested = evaluate(browser, "(() => { const scroll=document.querySelector('.candidate-scroll'); scroll.scrollTop=80; const background=document.querySelector('.theme-archive'); const bgEvent=new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:100}); background.dispatchEvent(bgEvent); const popupEvent=new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:100}); scroll.dispatchEvent(popupEvent); return new Promise(resolve => setTimeout(() => resolve({scrollTop:scroll.scrollTop, page:scrollY, active:document.activeElement.matches('[data-note]'), backgroundPrevented:bgEvent.defaultPrevented, popupPrevented:popupEvent.defaultPrevented}), 80)); })()")
        assert nested["scrollTop"] > 0 and abs(nested["page"] - locked_y) <= 1 and nested["active"] and nested["backgroundPrevented"] and not nested["popupPrevented"], nested
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.value='器械三头下压\\n悍马拉背二'; note.setSelectionRange('器械三头下压'.length,'器械三头下压'.length); note.dispatchEvent(new Event('input',{bubbles:true})); return true; })()")
        wait_for(browser, "document.querySelector('.candidate b')?.textContent === '器械三头下压'")
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.setSelectionRange(note.value.length,note.value.length); note.dispatchEvent(new Event('select',{bubbles:true})); return true; })()")
        wait_for(browser, "document.querySelector('.candidate b')?.textContent === '悍马拉背二'")
        switched = evaluate(browser, "({scrollTop:document.querySelector('.candidate-scroll').scrollTop, page:scrollY})")
        assert switched["scrollTop"] == 0 and abs(switched["page"] - locked_y) <= 1, switched
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.setSelectionRange(0,0); note.dispatchEvent(new Event('select',{bubbles:true})); return true; })()")
        wait_for(browser, "!document.querySelector('.candidate-overlay')")
        before_blur = evaluate(browser, "scrollY")
        evaluate(browser, "document.querySelector('[data-note]').blur(); true")
        wait_for(browser, "!document.documentElement.classList.contains('pwa-note-focused')")
        after_blur = evaluate(browser, "({page:scrollY, locked:document.documentElement.classList.contains('pwa-note-scroll-locked'), state:document.querySelector('[data-home-state]').dataset.homeState})")
        assert abs(after_blur["page"] - before_blur) <= 2 and not after_blur["locked"] and after_blur["state"] == "selected-expanded", after_blur
        command(browser, "Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True, "screenWidth": 390, "screenHeight": 844})
        print("PWA_HOME_EDITING_WORKSPACE: PASS")
    finally:
        if browser is not None:
            browser.close()
        stop(edge)
        stop(service)
        profile.cleanup()


if __name__ == "__main__":
    main()
