"""Browser test for the formal PWA phone-to-desktop handoff surface."""

from __future__ import annotations

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
PWA_ROOT = PROJECT / "mobile_viewer"


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
    raise AssertionError(f"browser condition timed out: {expression}; body={browser.evaluate('document.body.innerText')}")


def close_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


MOCK_CLOUDBASE = r"""
(() => {
  const rows = [];
  function matches(row, filter) { return Object.entries(filter || {}).every(([key, value]) => String(row[key] || '') === String(value || '').replace('{openid}', 'web-user')); }
  function query(filter = {}) {
    return {
      where(extra) { return query({ ...filter, ...extra }); },
      orderBy() { return this; },
      limit() { return this; },
      async get() { return { data: rows.filter(row => matches(row, filter)).sort((a, b) => b.received_at - a.received_at) }; },
      async update(payload) {
        rows.filter(row => matches(row, filter)).forEach(row => Object.assign(row, payload.data || {}));
        return { updated: rows.filter(row => matches(row, filter)).length };
      }
    };
  }
  const collection = {
    where(filter) { return query(filter); },
    async add(payload) { const row = { _id: `row-${rows.length + 1}`, _openid: 'web-user', ...payload.data }; rows.push(row); return { _id: row._id }; }
  };
  window.cloudbase = {
    init() { return { auth: () => ({ async getLoginState() { return true; }, async getAccessToken() { return { accessToken: 'test-token' }; } }), database: () => ({ collection() { return collection; } }) }; }
  };
})();
"""


def main() -> None:
    port, debug_port = _free_port(), _free_port()
    service: subprocess.Popen[str] | None = None
    edge: subprocess.Popen[bytes] | None = None
    browser: DevToolsSocket | None = None
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-formal-share-edge-")
    screenshot = Path(tempfile.gettempdir()) / "fitness-ledger-formal-share.png"
    try:
        service = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(PWA_ROOT)],
            cwd=PROJECT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        url = f"http://127.0.0.1:{port}/pwa/share.html?share_text=2026-08-16%20weight%2071%20kg&share_title=phone-note"
        edge = subprocess.Popen([str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--remote-debugging-port={debug_port}", f"--user-data-dir={profile.name}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = _wait_target(debug_port, "about:blank")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        command(browser, "Page.enable")
        command(browser, "Runtime.enable")
        command(browser, "Page.addScriptToEvaluateOnNewDocument", {"source": MOCK_CLOUDBASE})
        command(browser, "Page.navigate", {"url": url})
        wait(browser, "document.querySelector('[data-incoming-text]') !== null")
        incoming = browser.evaluate("document.querySelector('[data-incoming-text]').value")
        assert incoming == "2026-08-16 weight 71 kg", incoming
        browser.evaluate("document.querySelector('[data-action=send-incoming]').click()")
        wait(browser, "document.querySelector('[data-status=pending]') !== null && document.body.innerText.includes('2026-08-16 weight 71 kg')")
        assert browser.evaluate("document.body.innerText.includes('share-review') || document.body.innerText.includes('anonymous-review-fixture')") is False
        browser.evaluate("document.querySelector('[data-action=process-item]').click()")
        wait(browser, "document.querySelector('[data-status=processed]') !== null")
        result = command(browser, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        screenshot.write_bytes(base64.b64decode(result["data"]))
        print(json.dumps({"status": "PASS", "formal_share_target": True, "private_inbox_write": True, "processed_state": True, "candidate_trace_absent": True, "screenshot": str(screenshot)}, ensure_ascii=False))
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
