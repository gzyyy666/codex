"""Phone-size browser evidence for the body-area Movement Module projection."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from data_module_pwa_browser_test import _edge_path, _free_port, _wait_http, _wait_target
from data_module_formal_mirror_browser_e2e_test import DevToolsSocket


PROJECT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT / "tools" / "run_complex_set_superset_pwa_review.py"


def command(browser: DevToolsSocket, method: str, params: dict[str, Any] | None = None) -> Any:
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


def wait(browser: DevToolsSocket, expression: str, timeout: float = 12) -> Any:
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = browser.evaluate(expression)
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"browser condition timed out: {expression}")


def capture(browser: DevToolsSocket, output: Path) -> None:
    result = command(browser, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(result["data"]))


def close_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    port, debug_port = _free_port(), _free_port()
    service = edge = browser = None
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-body-area-pwa-edge-")
    try:
        service = subprocess.Popen([sys.executable, "-u", str(LAUNCHER), "--port", str(port)], cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        edge = subprocess.Popen([str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--remote-debugging-port={debug_port}", f"--user-data-dir={profile.name}", f"http://127.0.0.1:{port}/pwa/#reference"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = _wait_target(debug_port, f"http://127.0.0.1:{port}/pwa/")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        command(browser, "Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True, "screenWidth": 390, "screenHeight": 844})
        command(browser, "Page.reload", {"ignoreCache": True})
        wait(browser, "document.readyState==='complete' && !!document.querySelector('.reference-home') && !!document.querySelector(\"[data-action='select-module']\")")
        browser.evaluate("document.querySelector(\"[data-action='select-module'][data-part-id='chest']\").click(); true")
        wait(browser, "!!document.querySelector('.movement-summary')")
        browser.evaluate("document.querySelector('.movement-summary').click(); true")
        wait(browser, "!!document.querySelector('.movement-card') && document.querySelector('.movement-card').innerText.includes('Incline Press')")
        body_area = browser.evaluate("document.querySelector('.reference-home').innerText")
        assert "7.5kg × 6 + 5kg × 8 × 3组" in body_area and "超级组 A" in body_area and "第 1/2 个动作" in body_area, body_area
        assert browser.evaluate("document.querySelector('.movement-card .session-relation-detail').open") is False
        browser.evaluate("document.querySelector('.movement-card .session-relation-badge').click(); true")
        wait(browser, "document.querySelector('.movement-card .session-relation-detail').open === true")
        body_area_open = browser.evaluate("document.querySelector('.reference-home').innerText")
        assert "Triceps Pushdown" in body_area_open and "30kg × 12 × 3" in body_area_open and "#2" in body_area_open, body_area_open
        metrics = browser.evaluate("(() => { const page=document.querySelector('.reference-home'), card=document.querySelector('.movement-card'), tab=document.querySelector('.tabbar'); return {viewport:window.innerHeight, page_height:page?.getBoundingClientRect().height || 0, scroll_height:document.documentElement.scrollHeight, card_bottom:card?.getBoundingClientRect().bottom || 0, tab_top:tab?.getBoundingClientRect().top || window.innerHeight}; })()")
        capture(browser, args.output / "body-area-complex-superset-pwa.png")
        print(json.dumps({"status": "PASS", "screenshot": str(args.output / "body-area-complex-superset-pwa.png"), "complex_set_visible": True, "superset_members_visible": True, "layout_metrics": metrics}, ensure_ascii=False, indent=2))
    finally:
        if browser is not None:
            browser.close()
        close_process(edge)
        close_process(service)
        try:
            profile.cleanup()
        except PermissionError:
            pass


if __name__ == "__main__":
    main()
