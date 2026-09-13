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
        evaluate(browser, "document.querySelector('.home-module-pill').click()")
        wait_for(browser, "!!document.querySelector('.movement-preview')")
        overview = evaluate(browser, "(() => { const card=document.querySelector('.movement-summary').getBoundingClientRect(); const nav=document.querySelector('.tabbar').getBoundingClientRect(); return {cardBottom:card.bottom, navTop:nav.top, viewport:innerHeight}; })()")
        assert overview["cardBottom"] <= overview["navTop"] + 1, overview
        selected_tone = evaluate(browser, "document.querySelector('.reference-home').className")
        assert any(name in selected_tone for name in ("theme-color-amber", "theme-color-ember", "theme-color-teal", "theme-color-violet", "theme-color-blue", "theme-color-rose")), selected_tone
        evaluate(browser, "document.querySelector('[data-action=toggle-archive]').click()")
        wait_for(browser, "document.querySelector('[data-home-state]').dataset.homeState === 'selected-expanded' && !!document.querySelector('.theme-archive-head')")
        assert evaluate(browser, "Number.parseFloat(getComputedStyle(document.querySelector('[data-note]')).fontSize)") >= 16
        assert evaluate(browser, "getComputedStyle(document.querySelector('.note-stack')).position") == "sticky"
        assert evaluate(browser, "getComputedStyle(document.querySelector('.theme-archive-head')).position") == "sticky"
        wait_for(browser, "getComputedStyle(document.querySelector('.home-shell')).getPropertyValue('--expanded-note-height').trim() !== ''")
        sticky_layout = evaluate(browser, "(() => { const home=document.querySelector('.home-shell'); return {note:Number.parseFloat(getComputedStyle(home).getPropertyValue('--expanded-note-height')), strip:Number.parseFloat(getComputedStyle(home).getPropertyValue('--expanded-strip-height'))}; })()")
        assert sticky_layout["note"] > 0 and sticky_layout["strip"] > 0, sticky_layout
        scroll_target = evaluate(browser, "document.querySelector('.theme-archive-head').getBoundingClientRect().top + scrollY + 180")
        evaluate(browser, "(() => { const list=document.querySelector('.theme-archive-list'); list.style.minHeight='0'; list.style.height='1200px'; list.insertAdjacentHTML('beforeend', '<div data-test-scroll-content style=\"height:1200px\"></div>'); document.querySelector('.home-shell').insertAdjacentHTML('beforeend', '<div data-test-page-spacer style=\"height:1200px\"></div>'); })()")
        evaluate(browser, f"new Promise(resolve => setTimeout(() => {{ window.scrollTo(0, {scroll_target}); resolve(true); }}, 100))")
        evaluate(browser, "window.scrollTo(0, document.querySelector('.theme-archive-head').offsetTop + 180); window.dispatchEvent(new Event('scroll')); true")
        wait_for(browser, "document.querySelector('.home-shell').classList.contains('expanded-scroll-locked')")
        after_scroll = evaluate(browser, "new Promise(resolve => setTimeout(() => { const note=document.querySelector('.note-sheet').getBoundingClientRect(); const stack=document.querySelector('.note-stack').getBoundingClientRect(); const strip=document.querySelector('.theme-strip').getBoundingClientRect(); const head=document.querySelector('.theme-archive-head').getBoundingClientRect(); const list=document.querySelector('.theme-archive-list').getBoundingClientRect(); const home=document.querySelector('.home-shell'); resolve({noteTop:note.top, stackTop:stack.top, stripTop:strip.top, headTop:head.top, listTop:list.top, listClientHeight:document.querySelector('.theme-archive-list').clientHeight, listScrollHeight:document.querySelector('.theme-archive-list').scrollHeight, listOverflow:getComputedStyle(document.querySelector('.theme-archive-list')).overflowY, scrollY:scrollY, locked:home.classList.contains('expanded-scroll-locked'), position:getComputedStyle(document.querySelector('.note-stack')).position, archivePosition:getComputedStyle(document.querySelector('.theme-archive')).position}); }, 80))")
        assert after_scroll["noteTop"] <= 2, after_scroll
        assert after_scroll["stripTop"] >= after_scroll["noteTop"] + sticky_layout["note"] - 3, after_scroll
        assert after_scroll["headTop"] >= after_scroll["stripTop"] + sticky_layout["strip"] - 3, after_scroll
        assert after_scroll["locked"] is True and after_scroll["listOverflow"] in ("auto", "scroll"), after_scroll
        assert after_scroll["listScrollHeight"] > after_scroll["listClientHeight"], after_scroll
        assert after_scroll["archivePosition"] == "relative", after_scroll
        lock_scroll_y = after_scroll["scrollY"]
        evaluate(browser, f"window.scrollTo(0, {lock_scroll_y + 500}); true")
        locked_scroll = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(scrollY), 80))")
        assert abs(locked_scroll - lock_scroll_y) <= 1, {"lock_scroll_y": lock_scroll_y, "locked_scroll": locked_scroll}
        list_top = after_scroll["listTop"]
        evaluate(browser, "document.querySelector('.theme-archive-list').scrollTo(0, 220)")
        nested_scroll = evaluate(browser, "new Promise(resolve => setTimeout(() => { const list=document.querySelector('.theme-archive-list'); const note=document.querySelector('.note-sheet').getBoundingClientRect(); resolve({scrollTop:list.scrollTop, listTop:list.getBoundingClientRect().top, noteTop:note.top}); }, 80))")
        assert nested_scroll["scrollTop"] > 0 and abs(nested_scroll["listTop"] - list_top) <= 1 and nested_scroll["noteTop"] <= 2, nested_scroll
        first_module = evaluate(browser, "document.querySelector('[data-part-id]').dataset.partId")
        evaluate(browser, "document.querySelectorAll('.home-module-pill')[1].click()")
        wait_for(browser, "document.querySelector('[data-home-state]')?.dataset.homeState === 'selected-expanded' && !!document.querySelector('.home-module-pill.is-active')?.dataset.partId && document.querySelector('.home-module-pill.is-active').dataset.partId !== arguments[0]".replace("arguments[0]", repr(first_module)))
        assert evaluate(browser, "document.querySelector('[data-home-state]').dataset.homeState") == "selected-expanded"
        expanded_before_focus = evaluate(browser, "(() => { const sheet=document.querySelector('.note-sheet').getBoundingClientRect(); const editor=document.querySelector('[data-note]').getBoundingClientRect(); return {sheetHeight:sheet.height, editorHeight:editor.height}; })()")
        evaluate(browser, "document.querySelector('[data-note]').focus()")
        focused = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(document.querySelectorAll('.home-module-pill').length), 500))")
        assert focused == 8, focused
        evaluate(browser, "(() => { const note=document.querySelector('[data-note]'); note.value='器械三头下压'; note.dispatchEvent(new Event('input', {bubbles:true})); return true; })()")
        wait_for(browser, "!!document.querySelector('.candidate-overlay:not(.collapsed) .candidate b')")
        candidate_layout = evaluate(browser, "(() => { const candidate=document.querySelector('.candidate-overlay'); const note=document.querySelector('.note-sheet').getBoundingClientRect(); const editor=document.querySelector('[data-note]').getBoundingClientRect(); const rail=document.querySelector('.theme-strip'); const archive=document.querySelector('.theme-archive'); return {position:getComputedStyle(candidate).position, top:candidate.getBoundingClientRect().top, noteBottom:note.bottom, sheetHeight:note.height, editorHeight:editor.height, headerDisplay:getComputedStyle(document.querySelector('.home-header')).display, railDisplay:getComputedStyle(rail).display, archiveDisplay:getComputedStyle(archive).display, editorFont:Number.parseFloat(getComputedStyle(document.querySelector('[data-note]')).fontSize), viewportScale:window.visualViewport?.scale || 1, candidateName:document.querySelector('.candidate b')?.textContent}; })()")
        assert candidate_layout["position"] == "relative", candidate_layout
        assert candidate_layout["top"] >= candidate_layout["noteBottom"] - 1, candidate_layout
        assert candidate_layout["headerDisplay"] != "none", candidate_layout
        assert candidate_layout["railDisplay"] != "none" and candidate_layout["archiveDisplay"] != "none", candidate_layout
        assert candidate_layout["editorFont"] >= 16 and candidate_layout["viewportScale"] == 1, candidate_layout
        assert abs(candidate_layout["sheetHeight"] - expanded_before_focus["sheetHeight"]) <= 2, (expanded_before_focus, candidate_layout)
        assert abs(candidate_layout["editorHeight"] - expanded_before_focus["editorHeight"]) <= 2, (expanded_before_focus, candidate_layout)
        assert candidate_layout["candidateName"] == "器械三头下压", candidate_layout
        evaluate(browser, "(() => { const list=document.querySelector('.candidate-history-list'); const first=list.querySelector('.candidate-history'); list.append(first.cloneNode(true), first.cloneNode(true)); const values=first.querySelectorAll('.candidate-set-values b'); if(values.length===3){ values[0].textContent='127.5 kg'; values[1].textContent='15 次'; values[2].textContent='3 组'; } document.documentElement.classList.add('pwa-keyboard-open'); const home=document.querySelector('.home-shell').getBoundingClientRect(); const editor=document.querySelector('[data-note]').getBoundingClientRect(); const overlay=document.querySelector('.candidate-overlay'); overlay.style.setProperty('--keyboard-candidate-top', `${Math.round(editor.bottom-home.top-1)}px`); const scroll=overlay.querySelector('.candidate-scroll'); scroll.style.setProperty('--candidate-latest-height', `${Math.ceil(first.getBoundingClientRect().bottom-scroll.getBoundingClientRect().top+8)}px`); return true; })()")
        keyboard_layout = evaluate(browser, "new Promise(resolve => requestAnimationFrame(() => { const editor=document.querySelector('[data-note]').getBoundingClientRect(); const candidate=document.querySelector('.candidate-overlay').getBoundingClientRect(); const header=document.querySelector('.home-header').getBoundingClientRect(); const scroll=document.querySelector('.candidate-scroll'); const first=document.querySelector('.candidate-history'); const values=[...first.querySelectorAll('.candidate-set-values b')]; resolve({editorHeight:editor.height, editorBottom:editor.bottom, candidateTop:candidate.top, candidateHistories:[...document.querySelectorAll('.candidate-history')].filter(item => getComputedStyle(item).display !== 'none').length, columns:getComputedStyle(document.querySelector('.candidate-sets')).gridTemplateColumns, latestFullyVisible:first.getBoundingClientRect().bottom <= scroll.getBoundingClientRect().bottom+1, scrollHeight:scroll.scrollHeight, clientHeight:scroll.clientHeight, valuesFit:values.every(item => item.scrollWidth <= item.clientWidth+1), header:getComputedStyle(document.querySelector('.home-header')).display, headerHeight:header.height, rail:getComputedStyle(document.querySelector('.theme-strip')).display, archive:getComputedStyle(document.querySelector('.theme-archive')).display}); }))")
        assert 160 <= keyboard_layout["editorHeight"] <= 170, keyboard_layout
        assert abs(keyboard_layout["candidateTop"] - keyboard_layout["editorBottom"]) <= 2, keyboard_layout
        assert keyboard_layout["candidateHistories"] == 3, keyboard_layout
        assert len(keyboard_layout["columns"].split()) == 1, keyboard_layout
        assert keyboard_layout["latestFullyVisible"] and keyboard_layout["scrollHeight"] > keyboard_layout["clientHeight"], keyboard_layout
        assert keyboard_layout["valuesFit"], keyboard_layout
        assert keyboard_layout["header"] != "none" and keyboard_layout["headerHeight"] == 0, keyboard_layout
        assert keyboard_layout["rail"] != "none" and keyboard_layout["archive"] != "none", keyboard_layout
        evaluate(browser, "document.querySelector('.candidate-scroll').scrollTo(0, 60); true")
        candidate_scroll = evaluate(browser, "new Promise(resolve => setTimeout(() => resolve(document.querySelector('.candidate-scroll').scrollTop), 80))")
        assert candidate_scroll > 0, candidate_scroll
        evaluate(browser, "document.documentElement.classList.remove('pwa-keyboard-open'); true")
        evaluate(browser, "document.querySelector('[data-note]').blur(); true")
        wait_for(browser, "!document.documentElement.classList.contains('pwa-note-focused')")
        restored = evaluate(browser, "({rail:getComputedStyle(document.querySelector('.theme-strip')).display, archive:getComputedStyle(document.querySelector('.theme-archive')).display})")
        assert restored["rail"] != "none" and restored["archive"] != "none", restored
        evaluate(browser, "document.querySelector('.archive-collapse').click(); true")
        wait_for(browser, "document.querySelector('[data-home-state]').dataset.homeState === 'selected-collapsed'")
        collapsed_before_focus = evaluate(browser, "(() => { const sheet=document.querySelector('.note-sheet').getBoundingClientRect(); const editor=document.querySelector('[data-note]').getBoundingClientRect(); return {sheetHeight:sheet.height, editorHeight:editor.height}; })()")
        evaluate(browser, "document.querySelector('[data-note]').focus(); true")
        wait_for(browser, "document.documentElement.classList.contains('pwa-note-focused')")
        collapsed_focus = evaluate(browser, "(() => { const sheet=document.querySelector('.note-sheet').getBoundingClientRect(); const editor=document.querySelector('[data-note]').getBoundingClientRect(); return {header:getComputedStyle(document.querySelector('.home-header')).display, rail:getComputedStyle(document.querySelector('.theme-strip')).display, preview:getComputedStyle(document.querySelector('.movement-preview')).display, editorFont:Number.parseFloat(getComputedStyle(document.querySelector('[data-note]')).fontSize), sheetHeight:sheet.height, editorHeight:editor.height}; })()")
        assert collapsed_focus["header"] != "none" and collapsed_focus["rail"] != "none" and collapsed_focus["preview"] != "none", collapsed_focus
        assert collapsed_focus["editorFont"] == 16, collapsed_focus
        assert abs(collapsed_focus["sheetHeight"] - collapsed_before_focus["sheetHeight"]) <= 2, (collapsed_before_focus, collapsed_focus)
        assert abs(collapsed_focus["editorHeight"] - collapsed_before_focus["editorHeight"]) <= 2, (collapsed_before_focus, collapsed_focus)
        print("PWA_HOME_RENDER_STABILITY: PASS")
    finally:
        if browser is not None:
            browser.close()
        stop(edge)
        stop(service)
        profile.cleanup()


if __name__ == "__main__":
    main()
