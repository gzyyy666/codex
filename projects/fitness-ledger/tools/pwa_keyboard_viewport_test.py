"""Browser contract for the PWA note board under an iPhone keyboard viewport."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from data_module_browser_e2e_test import DevToolsSocket, _edge_path, _free_port, _wait_http, _wait_target


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
        if opcode != 1:
            continue
        decoded = json.loads(payload.decode("utf-8"))
        if decoded.get("id") == command_id:
            if "error" in decoded:
                raise AssertionError(decoded["error"])
            return decoded.get("result")


def wait_for(browser: DevToolsSocket, expression: str, timeout: float = 10) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if evaluate(browser, expression):
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out: {expression}")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def main() -> None:
    port, debug_port = _free_port(), _free_port()
    service = edge = None
    browser = None
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-keyboard-")
    try:
        service = subprocess.Popen([sys.executable, "-u", str(LAUNCHER), "--port", str(port)], cwd=PROJECT)
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        edge = subprocess.Popen([
            str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run",
            f"--remote-debugging-port={debug_port}", f"--user-data-dir={profile.name}",
            f"http://127.0.0.1:{port}/pwa/#reference",
        ])
        target = _wait_target(debug_port, f"http://127.0.0.1:{port}/pwa/")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        command(browser, "Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True,
            "screenWidth": 390, "screenHeight": 844,
        })
        command(browser, "Page.reload", {"ignoreCache": True})
        wait_for(browser, "!!document.querySelector('[data-note]')")
        evaluate(browser, """(() => {
          const input = document.querySelector('[data-note]');
          input.value = Array.from({length: 24}, (_, i) => `动作 ${i + 1} 30-12-1`).join('\\n');
          input.dispatchEvent(new Event('input', {bubbles:true}));
          document.querySelector('[data-candidate-region]').innerHTML = `<section class="candidates candidate-overlay"><div class="candidate-head"><span>可能相关动作 · 最近记录</span><button>收起</button></div><div class="candidate-scroll"><button class="candidate"><span class="candidate-main"><b>卧推</b><span class="candidate-history-list"><article class="candidate-history"><div class="candidate-history-head"><b>2026-09-11 · 第 1 个动作</b></div><div class="candidate-sets"><span>60 kg 8 次 1 组</span><span>50 kg 12 次 2 组</span></div></article></span></span></button></div></section>`;
          input.focus();
          Object.defineProperty(window, 'visualViewport', { configurable:true, value:{offsetTop:0,height:430} });
          window.dispatchEvent(new Event('resize'));
        })()""")
        wait_for(browser, "document.documentElement.dataset.pwaKeyboard === 'open' && document.documentElement.style.getPropertyValue('--pwa-note-height') !== ''")
        result = evaluate(browser, """(() => {
          const note=document.querySelector('.note-sheet').getBoundingClientRect();
          const editor=document.querySelector('.note-editor');
          const panel=document.querySelector('.candidate-overlay').getBoundingClientRect();
          return {noteTop:note.top,noteBottom:note.bottom,noteHeight:note.height,panelTop:panel.top,panelBottom:panel.bottom,
            editorOverflow:getComputedStyle(editor).overflowY,editorFont:getComputedStyle(editor).fontSize,
            editorScrollable:editor.scrollHeight>editor.clientHeight,stackPosition:getComputedStyle(document.querySelector('.note-stack')).position,
            homeShift:document.documentElement.style.getPropertyValue('--pwa-home-shift')};
        })()""")
        assert -1 <= result["noteTop"] <= 12, result
        assert 175 <= result["noteHeight"] <= 260, result
        assert result["noteBottom"] <= result["panelTop"] + 1, result
        assert result["panelBottom"] <= 430, result
        assert result["editorOverflow"] == "auto" and result["editorScrollable"], result
        assert result["editorFont"] == "16px" and result["stackPosition"] == "fixed", result
        assert result["homeShift"] == "", result

        evaluate(browser, "document.querySelector('[data-candidate-region]').innerHTML=''; window.dispatchEvent(new Event('resize'))")
        time.sleep(0.1)
        no_panel = evaluate(browser, "document.querySelector('.note-sheet').getBoundingClientRect().height")
        assert no_panel >= result["noteHeight"] + 150, {"withPanel": result["noteHeight"], "withoutPanel": no_panel}
        print("PWA_KEYBOARD_VIEWPORT: PASS")
    finally:
        if browser:
            browser.close()
        stop(edge)
        stop(service)
        profile.cleanup()


if __name__ == "__main__":
    main()
