"""Real browser E2E for the isolated self-service Data Module Candidate.

The harness starts the Candidate launcher and a temporary headless Edge only.
It uses the DevTools websocket with the Python standard library so the test
does not add a browser automation dependency to the product candidate.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "tools" / "run_data_module_candidate_preview.py"


def _read_exact(sock: socket.socket, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("browser websocket closed unexpectedly")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class DevToolsSocket:
    def __init__(self, websocket_url: str):
        parsed = urllib.parse.urlparse(websocket_url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {parsed.path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.sock.sendall(request)
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(4096)
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError(f"browser websocket handshake failed: {response[:200]!r}")
        self.next_id = 1

    def _send_frame(self, payload: bytes, opcode: int = 1) -> None:
        first = 0x80 | opcode
        length = len(payload)
        mask = os.urandom(4)
        if length < 126:
            header = bytes([first, 0x80 | length])
        elif length < 65536:
            header = bytes([first, 0x80 | 126]) + struct.pack("!H", length)
        else:
            header = bytes([first, 0x80 | 127]) + struct.pack("!Q", length)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def _receive_frame(self) -> tuple[int, bytes]:
        first, second = _read_exact(self.sock, 2)
        opcode = first & 0x0F
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", _read_exact(self.sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _read_exact(self.sock, 8))[0]
        masked = second & 0x80
        mask = _read_exact(self.sock, 4) if masked else b""
        payload = _read_exact(self.sock, length)
        if masked:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return opcode, payload

    def evaluate(self, expression: str) -> Any:
        command_id = self.next_id
        self.next_id += 1
        message = json.dumps({
            "id": command_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "awaitPromise": True, "returnByValue": True},
        }).encode("utf-8")
        self._send_frame(message)
        while True:
            opcode, payload = self._receive_frame()
            if opcode == 9:
                self._send_frame(payload, opcode=10)
                continue
            if opcode == 8:
                raise RuntimeError("browser websocket closed")
            if opcode != 1:
                continue
            decoded = json.loads(payload.decode("utf-8"))
            if decoded.get("id") != command_id:
                continue
            result = decoded.get("result", {}).get("result", {})
            if "exceptionDetails" in decoded.get("result", {}):
                raise AssertionError(decoded["result"]["exceptionDetails"])
            if result.get("subtype") == "error":
                raise AssertionError(result)
            return result.get("value")

    def close(self) -> None:
        try:
            self._send_frame(b"", opcode=8)
        except OSError:
            pass
        self.sock.close()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_http(url: str, timeout: float = 15) -> bytes:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - startup timing
            last_error = exc
            time.sleep(0.15)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def _edge_path() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("Microsoft Edge executable is not installed")


def _wait_target(debug_port: int, target_url: str, timeout: float = 15) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/list", timeout=2) as response:
                targets = json.loads(response.read().decode("utf-8"))
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl") and target_url in target.get("url", ""):
                    return target
        except Exception:  # pragma: no cover - startup timing
            pass
        time.sleep(0.15)
    raise RuntimeError("timed out waiting for Edge DevTools page target")


def _wait(browser: DevToolsSocket, expression: str, timeout: float = 10) -> Any:
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = browser.evaluate(expression)
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"browser condition timed out: {expression}")


def _call(browser: DevToolsSocket, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    expression = f"""(async () => {{
        const response = await fetch({json.dumps(path)}, {json.dumps({
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        })});
        return {{status: response.status, body: await response.json()}};
    }})()"""
    result = browser.evaluate(expression)
    assert isinstance(result, dict), result
    return result


def _set(browser: DevToolsSocket, element_id: str, value: str) -> None:
    expression = f"""(() => {{
        const element = document.getElementById({json.dumps(element_id)});
        element.value = {json.dumps(value)};
        element.dispatchEvent(new Event('input', {{bubbles: true}}));
        element.dispatchEvent(new Event('change', {{bubbles: true}}));
        return true;
    }})()"""
    assert browser.evaluate(expression) is True


def _click(browser: DevToolsSocket, selector: str) -> None:
    expression = f"""(() => {{
        const element = document.querySelector({json.dumps(selector)});
        if (!element) return false;
        element.click();
        return true;
    }})()"""
    assert browser.evaluate(expression) is True, selector


def _catalog(browser: DevToolsSocket) -> dict[str, Any]:
    result = browser.evaluate("(async () => await (await fetch('/api/data-modules/catalog')).json())()")
    assert isinstance(result, dict), result
    return result


def main() -> None:
    service_port = _free_port()
    debug_port = _free_port()
    target_url = f"http://127.0.0.1:{service_port}/data-module-candidate.html"
    service_process = subprocess.Popen(
        [sys.executable, "-u", str(LAUNCHER), "--port", str(service_port)],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    edge_process: subprocess.Popen[bytes] | None = None
    browser: DevToolsSocket | None = None
    try:
        _wait_http(target_url)
        edge_user_data = tempfile.TemporaryDirectory(prefix="fitness-ledger-edge-e2e-")
        edge_process = subprocess.Popen(
            [
                str(_edge_path()),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={edge_user_data.name}",
                target_url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        target = _wait_target(debug_port, target_url)
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        _wait(browser, "document.readyState === 'complete' && document.body.innerText.includes('Self-Service Data Module Candidate')")

        _set(browser, "category-label", "Browser Review Category")
        _set(browser, "category-id", "browser_review_category")
        _set(browser, "category-order", "800")
        _click(browser, "#category-preview")
        _wait(browser, "document.getElementById('category-save').disabled === false")
        category_preview = browser.evaluate("JSON.parse(document.getElementById('category-result').textContent)")
        assert category_preview["write_attempted"] is False
        _click(browser, "#category-save")
        _wait(browser, "(async () => (await (await fetch('/api/data-modules/catalog')).json()).categories.some(item => item.category_id === 'browser_review_category'))()")

        _set(browser, "module-label", "Browser Review Numeric")
        _set(browser, "actual-unit", "bpm")
        _set(browser, "display-unit", "bpm")
        _set(browser, "module-aliases", "browser pulse\nreview pulse")
        _set(browser, "minimum", "20")
        _set(browser, "maximum", "240")
        browser.evaluate("document.getElementById('module-category').value = 'browser_review_category'; true")
        _click(browser, "#module-preview")
        _wait(browser, "document.getElementById('module-save').disabled === false")
        module_preview = browser.evaluate("JSON.parse(document.getElementById('module-result').textContent)")
        assert module_preview["write_attempted"] is False
        module_id = next(item["module_id"] for item in module_preview["after"]["modules"] if item["label"] == "Browser Review Numeric")
        _click(browser, "#module-save")
        _wait(browser, f"(async () => (await (await fetch('/api/data-modules/catalog')).json()).modules.some(item => item.module_id === {json.dumps(module_id)}))()")
        before_history = _call(browser, f"/api/data-modules/history?module_id={urllib.parse.quote(module_id)}")

        _set(browser, "raw", "今天 browser pulse 58")
        _click(browser, "#record-preview")
        _wait(browser, "document.getElementById('record-save').disabled === false")
        record_preview = browser.evaluate("JSON.parse(document.getElementById('record-result').textContent)")
        assert record_preview["write_attempted"] is False
        after_preview_history = _call(browser, f"/api/data-modules/history?module_id={urllib.parse.quote(module_id)}")
        assert len(after_preview_history["body"].get("history", [])) == len(before_history["body"].get("history", []))
        _click(browser, "#record-save")
        _wait(browser, f"(async () => (await (await fetch('/api/data-modules/history?module_id={urllib.parse.quote(module_id)}')).json()).history.length === 1)()")

        _click(browser, f"[data-module-edit={json.dumps(module_id)}]")
        _set(browser, "module-label", "Browser Review Numeric Edited")
        _set(browser, "module-aliases", "edited browser pulse")
        _set(browser, "module-slot", "history")
        _set(browser, "module-order", "877")
        _click(browser, "#module-preview")
        _wait(browser, "document.getElementById('module-save').disabled === false")
        _click(browser, "#module-save")
        _wait(browser, f"(async () => {{ const item = (await (await fetch('/api/data-modules/catalog')).json()).modules.find(item => item.module_id === {json.dumps(module_id)}); return item && item.label === 'Browser Review Numeric Edited' && item.presentation.slot === 'history'; }})()")

        _click(browser, f"[data-module-action={json.dumps(module_id)}]")
        _wait(browser, f"(async () => (await (await fetch('/api/data-modules/catalog')).json()).modules.find(item => item.module_id === {json.dumps(module_id)}).status === 'retired')()")
        negative_record = _call(browser, "/api/data-modules/preview", {"raw": "今天 edited browser pulse 59"})
        assert negative_record["status"] == 400
        assert negative_record["body"]["code"] == "MODULE_NOT_RECORDABLE"
        _click(browser, f"[data-module-action={json.dumps(module_id)}]")
        _wait(browser, f"(async () => (await (await fetch('/api/data-modules/catalog')).json()).modules.find(item => item.module_id === {json.dumps(module_id)}).status === 'active')()")

        _click(browser, "[data-category-action='browser_review_category']")
        _wait(browser, "(async () => (await (await fetch('/api/data-modules/catalog')).json()).categories.find(item => item.category_id === 'browser_review_category').status === 'retired')()")
        negative_create = _call(browser, "/api/data-modules/definition-preview", {"kind": "module", "action": "create", "values": {"label": "Blocked", "category_id": "browser_review_category", "data_type": "quantity", "actual_unit": "bpm"}})
        assert negative_create["status"] == 400
        assert negative_create["body"]["code"] == "CATEGORY_NOT_RECORDABLE"
        _click(browser, "[data-category-action='browser_review_category']")
        _wait(browser, "(async () => (await (await fetch('/api/data-modules/catalog')).json()).categories.find(item => item.category_id === 'browser_review_category').status === 'active')()")

        _click(browser, "#refresh-downstream")
        _wait(browser, "document.getElementById('downstream').textContent.includes('network_request_made')")
        downstream = json.loads(browser.evaluate("document.getElementById('downstream').textContent"))
        assert downstream["cloud_dry_run"]["network_request_made"] is False
        assert downstream["normal_export"]["module_count"] >= 3

        _click(browser, "#data-check")
        _wait(browser, "document.getElementById('data-check-result').textContent.length > 0 && !document.getElementById('data-check-result').textContent.includes('等待检查')")
        data_check = json.loads(browser.evaluate("document.getElementById('data-check-result').textContent"))
        assert isinstance(data_check, list)
        print(json.dumps({
            "status": "PASS",
            "browser": "Microsoft Edge headless",
            "real_page": target_url,
            "module_id": module_id,
            "preview_zero_write": True,
            "confirm_history": True,
            "edit_placement": True,
            "retire_reenable": True,
            "new_category_retire_gate": True,
            "downstream_network_request_made": downstream["cloud_dry_run"]["network_request_made"],
            "data_check_issue_count": len(data_check),
        }, ensure_ascii=False, indent=2))
    finally:
        if browser is not None:
            browser.close()
        if edge_process is not None:
            edge_process.terminate()
            try:
                edge_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                edge_process.kill()
        if service_process.poll() is None:
            service_process.terminate()
            try:
                service_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                service_process.kill()


if __name__ == "__main__":
    main()
