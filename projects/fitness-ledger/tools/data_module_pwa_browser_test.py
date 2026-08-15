"""Phone-size browser acceptance for PWA Data Module placement."""

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

from data_module_browser_e2e_test import DevToolsSocket, _edge_path, _free_port, _wait_http, _wait_target


PROJECT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT / "tools" / "run_data_module_pwa_review.py"


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


def navigate(browser: DevToolsSocket, route: str, selector: str) -> None:
    browser.evaluate(f"location.hash={json.dumps(route)}")
    wait(browser, f"document.readyState==='complete' && !!document.querySelector({json.dumps(selector)}) && !document.body.innerText.includes('正在读取')")
    assert browser.evaluate("document.documentElement.scrollWidth===document.documentElement.clientWidth") is True
    assert "???" not in str(browser.evaluate("document.body.innerText"))


def capture(browser: DevToolsSocket, output: Path, filename: str) -> None:
    result = command(browser, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    output.mkdir(parents=True, exist_ok=True)
    (output / filename).write_bytes(base64.b64decode(result["data"]))


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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(tempfile.mkdtemp(prefix="fitness-ledger-pwa-browser-evidence-"))
    port, debug_port = _free_port(), _free_port()
    service: subprocess.Popen[str] | None = None
    edge: subprocess.Popen[bytes] | None = None
    browser: DevToolsSocket | None = None
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-edge-")
    try:
        service = subprocess.Popen(
            [sys.executable, "-u", str(LAUNCHER), "--port", str(port)],
            cwd=PROJECT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        url = f"http://127.0.0.1:{port}/pwa/#reference"
        edge = subprocess.Popen(
            [
                str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={profile.name}", url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        target = _wait_target(debug_port, f"http://127.0.0.1:{port}/pwa/")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        command(browser, "Emulation.setDeviceMetricsOverride", {
            "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True,
            "screenWidth": 390, "screenHeight": 844,
        })
        command(browser, "Page.reload", {"ignoreCache": True})
        wait(browser, "document.readyState==='complete' && !!document.querySelector('.area-list') && document.body.innerText.includes('睡眠评分')")

        widget = browser.evaluate("(() => { const x=document.querySelector('.module-page-widget'); const r=x.getBoundingClientRect(); return {text:x.innerText,width:r.width,right:innerWidth-r.right,innerWidth,clientWidth:document.documentElement.clientWidth,visualWidth:visualViewport.width}; })()")
        assert "睡眠评分" in widget["text"] and "7" in widget["text"]
        assert widget["width"] < 180 and abs(widget["right"]) < 2, widget
        capture(browser, output, "01-home-widget.png")

        navigate(browser, "body", ".body-slip")
        body_text = browser.evaluate("document.querySelector('.body-slip').innerText")
        assert "腰围" in body_text and "82.5 cm" in body_text
        capture(browser, output, "02-body-native.png")

        navigate(browser, "diet", ".diet-slip")
        diet_text = browser.evaluate("document.body.innerText")
        assert "2026-08-14" in diet_text and "肌酸" in diet_text and "5 g" in diet_text
        assert browser.evaluate("document.querySelectorAll('.diet-slip').length") == 2
        capture(browser, output, "03-diet-module-only-date.png")

        navigate(browser, "training", ".training-slip")
        training_text = browser.evaluate("document.body.innerText")
        assert "2026-08-13" in training_text and "训练状态" in training_text and "8" in training_text
        assert browser.evaluate("document.querySelectorAll('.training-slip').length") == 2
        capture(browser, output, "04-training-module-only-date.png")

        navigate(browser, "record?date=2026-08-15&from=body", ".record-page")
        detail_text = browser.evaluate("document.body.innerText")
        assert "腰围" in detail_text and "82.5 cm" in detail_text
        assert "其他记录" in detail_text and "睡眠评分" in detail_text and "握力状态" in detail_text
        assert browser.evaluate("getComputedStyle(document.querySelector('.route-back')).position") == "fixed"
        capture(browser, output, "05-detail-native-and-other.png")

        navigate(browser, "record?date=2026-08-14&from=diet", ".diet-section")
        detail_diet_text = browser.evaluate("document.querySelector('.diet-section').innerText")
        assert "肌酸" in detail_diet_text and "5 g" in detail_diet_text
        capture(browser, output, "06-detail-module-only.png")

        navigate(browser, "movement?id=missing", ".movement-page")
        movement_text = browser.evaluate("document.body.innerText")
        assert "握力状态" in movement_text and "6" in movement_text
        capture(browser, output, "07-movement-edge-widget.png")

        print(f"DATA_MODULE_PWA_BROWSER_OK screenshots={output}")
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
