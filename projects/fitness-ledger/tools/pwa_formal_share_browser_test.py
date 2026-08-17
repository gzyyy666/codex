"""Browser test for the formal PWA in-app phone handoff surface."""

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
  window.__shareRows = rows;
  function matches(row, filter) { return Object.entries(filter || {}).every(([key, value]) => String(row[key] || '') === String(value || '').replace('{openid}', 'web-user')); }
  function query(filter = {}) {
    return {
      where(extra) { return query({ ...filter, ...extra }); },
      orderBy() { return this; },
      limit() { return this; },
      async get() { return { data: rows.filter(row => matches(row, filter)).sort((a, b) => b.received_at - a.received_at) }; },
      async update(payload) { rows.filter(row => matches(row, filter)).forEach(row => Object.assign(row, payload.data || payload || {})); return { updated: 1 }; }
    };
  }
  const collection = {
    where(filter) { return query(filter); },
    doc(id) { return { async update(payload) { Object.assign(rows.find(row => row._id === id) || {}, payload.data || {}); }, async remove() { const index = rows.findIndex(row => row._id === id); if (index >= 0) rows.splice(index, 1); } }; },
    async add(payload) { const row = { _id: `row-${rows.length + 1}`, _openid: 'web-user', ...(payload.data || payload) }; rows.push(row); return { _id: row._id }; }
  };
  window.cloudbase = { init() { return { auth: () => ({ async getLoginState() { return { loginType: 'CUSTOM', isCustomAuth: true, user: { uid: 'web-user' } }; } }), database: () => ({ collection() { return collection; } }) }; } };
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { async writeText(value) { window.__copied = value; } } });
})();
"""


def main() -> None:
    port, debug_port = _free_port(), _free_port()
    service: subprocess.Popen[str] | None = None
    edge: subprocess.Popen[bytes] | None = None
    browser: DevToolsSocket | None = None
    profile = tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-in-app-edge-")
    screenshot = Path(tempfile.gettempdir()) / "fitness-ledger-pwa-in-app.png"
    try:
        service = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(PWA_ROOT)],
            cwd=PROJECT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_http(f"http://127.0.0.1:{port}/pwa/")
        url = f"http://127.0.0.1:{port}/pwa/share.html?share_text=2026-08-16%20weight%2071%20kg&share_title=phone-note&share_mode=outbound"
        edge = subprocess.Popen([str(_edge_path()), "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", f"--remote-debugging-port={debug_port}", f"--user-data-dir={profile.name}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = _wait_target(debug_port, "about:blank")
        browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
        command(browser, "Page.enable")
        command(browser, "Runtime.enable")
        command(browser, "Page.addScriptToEvaluateOnNewDocument", {"source": MOCK_CLOUDBASE})
        command(browser, "Page.navigate", {"url": url})
        wait(browser, "document.querySelector('[data-share-draft]') !== null")
        assert browser.evaluate("location.pathname.endsWith('/index.html')") is True
        assert browser.evaluate("document.querySelector('[data-share-draft]').value") == "2026-08-16 weight 71 kg"
        assert browser.evaluate("document.body.innerText.includes('确认并发送')") is True
        assert browser.evaluate("document.body.innerText.includes('不会写入手机正式档案')") is True
        browser.evaluate("document.querySelector('[data-action=send-training-note]').click()")
        wait(browser, "document.body.innerText.includes('已发送到云端')")
        assert browser.evaluate("document.querySelector('[data-share-draft]') === null") is True
        assert browser.evaluate("document.querySelector('.copy-feedback-toast') !== null") is True
        assert browser.evaluate("window.__shareRows.length === 1 && window.__shareRows[0].text === '2026-08-16 weight 71 kg'") is True

        command(browser, "Page.navigate", {"url": f"http://127.0.0.1:{port}/pwa/index.html#reference?part=chest"})
        wait(browser, "document.querySelector('.part-hero') !== null")
        browser.evaluate("document.querySelector('.part-hero').click()")
        wait(browser, "document.querySelector('[data-note]') !== null")
        browser.evaluate("const n=document.querySelector('[data-note]'); n.value='今天训练 4 组'; n.dispatchEvent(new Event('input',{bubbles:true}))")
        browser.evaluate("document.querySelector('[data-action=expand-note]').click()")
        wait(browser, "document.querySelector('[data-action=send-training-note]') !== null")
        assert browser.evaluate("document.body.innerText.includes('确认并发送')") is True
        browser.evaluate("document.querySelector('[data-action=close-share-panel]').click()")
        wait(browser, "document.querySelector('[data-note]') !== null")
        assert browser.evaluate("document.querySelector('[data-action=expand-note]').textContent.trim() === '发送到电脑'") is True
        browser.evaluate("document.querySelector('[data-action=copy-note]').click()")
        wait(browser, "document.querySelector('.copy-feedback-toast') !== null")
        assert browser.evaluate("document.body.innerText.includes('已复制到剪贴板')") is True
        assert browser.evaluate("window.__copied === '今天训练 4 组'") is True
        result = command(browser, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        screenshot.write_bytes(base64.b64decode(result["data"]))
        print(json.dumps({"status": "PASS", "in_app_share_target": True, "second_confirmation": True, "private_inbox_write": True, "copy_feedback": True, "legacy_share_redirected": True, "screenshot": str(screenshot)}, ensure_ascii=False))
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
