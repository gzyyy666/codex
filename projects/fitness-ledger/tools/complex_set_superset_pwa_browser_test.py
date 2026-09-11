"""Phone-size browser evidence for Session Superset relation details."""

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
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-complex-superset-pwa-edge-")
    try:
        service = subprocess.Popen([sys.executable, "-u", str(LAUNCHER), "--port", str(port)], cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        edge = subprocess.Popen([str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--remote-debugging-port={debug_port}", f"--user-data-dir={profile.name}", f"http://127.0.0.1:{port}/pwa/#record?mode=training&sessionId=session-complex-superset&date=2099-01-05"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = _wait_target(debug_port, f"http://127.0.0.1:{port}/pwa/")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        command(browser, "Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True, "screenWidth": 390, "screenHeight": 844})
        command(browser, "Page.reload", {"ignoreCache": True})
        wait(browser, "document.readyState==='complete' && !!document.querySelector('.training-session-only') && document.body.innerText.includes('Incline Press')")
        before = browser.evaluate("document.body.innerText")
        assert "超级组 A" in before and "第 1/2 个动作" in before and "同组成员" not in before, before
        assert browser.evaluate("document.querySelector('.session-relation-detail').open") is False
        browser.evaluate("document.querySelector('.session-relation-badge').click(); true")
        wait(browser, "document.querySelector('.session-relation-detail').open === true")
        after = browser.evaluate("document.body.innerText")
        assert "小 session · 组内顺序与组数据" in after and "当前动作" in after and "Triceps Pushdown" in after and "30kg × 12 × 3" in after and "#2" in after, after
        assert browser.evaluate("document.documentElement.scrollWidth===document.documentElement.clientWidth") is True
        capture(browser, args.output / "superset-relation-detail-pwa.png")
        print(json.dumps({"status": "PASS", "screenshot": str(args.output / "superset-relation-detail-pwa.png"), "tap_fallback": True, "members_visible": True}, ensure_ascii=False, indent=2))
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
