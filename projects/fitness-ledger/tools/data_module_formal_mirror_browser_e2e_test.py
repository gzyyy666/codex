"""Browser acceptance test for the Formal Web Integrated Review Mirror.

This uses the installed Microsoft Edge DevTools websocket directly.  It keeps
the review path dependency-free and exercises the real Web shell, not a DOM
mock or the separate engineering candidate page.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from data_module_browser_e2e_test import (
    DevToolsSocket,
    _click,
    _edge_path,
    _free_port,
    _wait_http,
    _wait_target,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "tools" / "run_data_module_formal_mirror.py"


def _wait(browser: DevToolsSocket, expression: str, timeout: float = 12) -> Any:
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = browser.evaluate(expression)
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"browser condition timed out: {expression}")


def _command(browser: DevToolsSocket, method: str, params: dict[str, Any] | None = None) -> Any:
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


def _set_css(browser: DevToolsSocket, selector: str, value: str) -> None:
    expression = f"""(() => {{
        const element=document.querySelector({json.dumps(selector)});
        if(!element)return false;
        element.value={json.dumps(value)};
        element.dispatchEvent(new Event('input',{{bubbles:true}}));
        element.dispatchEvent(new Event('change',{{bubbles:true}}));
        return true;
    }})()"""
    assert browser.evaluate(expression) is True, selector


def _set_checked(browser: DevToolsSocket, selector: str, checked: bool) -> None:
    expression = f"""(() => {{
        const element=document.querySelector({json.dumps(selector)});
        if(!element)return false;
        element.checked={str(checked).lower()};
        element.dispatchEvent(new Event('change',{{bubbles:true}}));
        return true;
    }})()"""
    assert browser.evaluate(expression) is True, selector


def _select(browser: DevToolsSocket, selector: str, value: str) -> None:
    _set_css(browser, selector, value)


def _click_dataset(browser: DevToolsSocket, selector: str, key: str, value: str) -> None:
    expression = f"""(() => {{
        const element=[...document.querySelectorAll({json.dumps(selector)})].find(item=>item.dataset[{json.dumps(key)}]==={json.dumps(value)});
        if(!element)return false;element.click();return true;
    }})()"""
    assert browser.evaluate(expression) is True, f"{selector}[data-{key}={value}]"


def _json_get(browser: DevToolsSocket, path: str) -> dict[str, Any]:
    result = browser.evaluate(f"(async()=>await (await fetch({json.dumps(path)})).json())()")
    assert isinstance(result, dict), result
    return result


def _json_post(browser: DevToolsSocket, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = browser.evaluate(f"""(async()=>{{
      const response=await fetch({json.dumps(path)},{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({json.dumps(payload,ensure_ascii=False)})}});
      return {{status:response.status,body:await response.json()}};
    }})()""")
    assert isinstance(result, dict), result
    return result


def _close_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _safe_cleanup(directory: tempfile.TemporaryDirectory[str] | None) -> None:
    if directory is None:
        return
    try:
        directory.cleanup()
    except PermissionError:
        # Edge may release a Crashpad dump just after its process exits. The
        # directory is already outside the repository; leaving that OS temp
        # directory for the normal cleanup sweep is safer than failing a
        # completed browser assertion.
        pass


def _start_service(port: int, sandbox: str) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [sys.executable, "-u", str(LAUNCHER), "--port", str(port), "--sandbox", sandbox],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_http(f"http://127.0.0.1:{port}/api/health")
    return process


def _start_browser(port: int) -> tuple[subprocess.Popen[bytes], DevToolsSocket, tempfile.TemporaryDirectory[str]]:
    debug_port = _free_port()
    target_url = f"http://127.0.0.1:{port}/"
    user_data = tempfile.TemporaryDirectory(prefix="fitness-ledger-formal-mirror-edge-")
    process = subprocess.Popen(
        [
            str(_edge_path()),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data.name}",
            target_url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    target = _wait_target(debug_port, target_url)
    browser = DevToolsSocket(str(target["webSocketDebuggerUrl"]))
    _wait(browser, "document.readyState==='complete' && !!document.querySelector('.sidebar') && document.body.innerText.includes('Daily Entry') && window.__fitnessLedgerFormalMirrorReady===true")
    return process, browser, user_data


def main() -> None:
    port = _free_port()
    service: subprocess.Popen[str] | None = None
    edge: subprocess.Popen[bytes] | None = None
    browser: DevToolsSocket | None = None
    edge_data: tempfile.TemporaryDirectory[str] | None = None
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-formal-mirror-sandbox-")
    screenshot_path = Path(tempfile.gettempdir()) / "fitness-ledger-formal-mirror-review.png"
    try:
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        _command(browser, "Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick')")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        _click(browser, "[data-dm-llm-template]")
        _wait(browser, "!!document.querySelector('.entry-template-json')")
        assert "fitness-ledger-llm-entry-template-v1" in browser.evaluate("document.querySelector('.entry-template-json').textContent")
        _click(browser, "[data-close]")
        _set_css(browser, "#raw-entry", "2026-08-12 \u6668\u95f4\u8109\u640f 58")
        _click(browser, "#parse")
        _wait(browser, "!!document.querySelector('[data-dm-submit-definition]')")
        assert browser.evaluate("document.querySelector('[name=label]').value") == "\u6668\u95f4\u8109\u640f"
        _set_css(browser, "[name=actual_unit]", "bpm")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!!document.querySelector('[data-dm-confirm-record]')")
        before_save = len(_json_get(browser, "/api/data-modules/export").get("records", []))
        _click(browser, "[data-dm-confirm-record]")
        _wait(browser, "!!document.querySelector('[data-dm-go-body]')")
        after_preview = len(_json_get(browser, "/api/data-modules/export").get("records", []))
        assert after_preview == before_save + 1, (before_save, after_preview)
        first_catalog = _json_get(browser, "/api/data-modules/product-catalog")
        pulse = next(item for item in first_catalog["modules"] if item["label"] == "\u6668\u95f4\u8109\u640f")
        pulse_id = pulse["module_id"]
        assert pulse["category_id"] == "body" and pulse["display_surface"] == "category_page" and pulse["record_level"] == "daily_scalar", pulse
        _click(browser, "[data-dm-go-body]")
        _wait(browser, "!!document.querySelector('.archive-heading')")
        _wait(browser, "!!document.querySelector('.dm-inline-metrics')")
        body_snapshot=browser.evaluate("({url:location.href,hasShelf:!!document.querySelector('.dm-surface-shelf'),hasCompact:!!document.querySelector('.dm-inline-metrics'),text:document.body.innerText.slice(0,1200)})")
        assert not body_snapshot["hasShelf"] and body_snapshot["hasCompact"] and "\u6668\u95f4\u8109\u640f" in body_snapshot["text"], body_snapshot
        screenshot_data = _command(browser, "Page.captureScreenshot", {"format": "png"})
        screenshot_path.write_bytes(base64.b64decode(screenshot_data["data"]))
        diet_discovery = _json_post(browser, "/api/data-modules/discover", {"raw": "\u4eca\u5929\u6bcf\u65e5\u808c\u9178 5 g"})
        assert diet_discovery["status"] == 200 and diet_discovery["body"]["candidate"]["suggested_category_id"] == "diet" and diet_discovery["body"]["candidate"]["unit"] == "g", diet_discovery

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools')")
        _wait(browser, "!!document.querySelector('.dm-tools-entry')")
        _click(browser, ".dm-tools-entry")
        _wait(browser, "!!document.querySelector('.dm-management-page')")
        _wait(browser, "!!document.querySelector('[data-dm-release-readiness]')")
        _click(browser, "[data-dm-release-readiness]")
        _wait(browser, "!!document.querySelector('.detail-list')")
        readiness_text = browser.evaluate("document.querySelector('.detail-list').innerText")
        assert "Cloud dry-run" in readiness_text and "Mini contract" in readiness_text and "无网络" in readiness_text, readiness_text
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.root.innerHTML='' ")

        # Management create: a second module in the existing Body category.
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u65e5\u95f4\u4f53\u6e29")
        _set_css(browser, "[name=actual_unit]", "C")
        _set_css(browser, "[name=aliases]", "\u65e5\u95f4\u4f53\u6e29")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        catalog = _json_get(browser, "/api/data-modules/product-catalog")
        temperature = next(item for item in catalog["modules"] if item["label"] == "\u65e5\u95f4\u4f53\u6e29")
        temperature_id = temperature["module_id"]
        template_after_module = _json_get(browser, "/api/data-modules/llm-template")
        assert any(item["module_id"] == temperature_id for item in template_after_module["modules"]), template_after_module

        # Diet follows the existing P / C / F surface instead of creating a Diet sub-page.
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u6bcf\u65e5\u808c\u9178")
        _select(browser, "[name=category_id]", "diet")
        _set_css(browser, "[name=actual_unit]", "g")
        _select(browser, "[name=placement]", "detail")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        catalog = _json_get(browser, "/api/data-modules/product-catalog")
        creatine = next(item for item in catalog["modules"] if item["label"] == "\u6bcf\u65e5\u808c\u9178")
        assert creatine["category_id"] == "diet" and creatine["display_surface"] == "category_page" and creatine["placement"] == "detail", creatine
        creatine_record_preview = _json_post(browser, "/api/data-modules/preview", {"raw": "2026-08-12 \u6bcf\u65e5\u808c\u9178 5 g"})
        _json_post(browser, "/api/data-modules/save", {"preview": creatine_record_preview["body"], "confirmed": True})
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('body')")
        _wait(browser, "!!document.querySelector('.record-open')")
        _click(browser, ".record-open")
        _wait(browser, "!!document.querySelector('.structured-detail-modal')")
        _wait(browser, "!!document.querySelector('.dm-detail-metrics')")
        assert browser.evaluate("document.body.innerText.includes('\u6bcf\u65e5\u808c\u9178')")
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.root.innerHTML=''")
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools',{panel:'data-modules'})")
        _wait(browser, "!!document.querySelector('.dm-management-page')")

        # Unclassified data uses the normal flow: choose "Other Extensions";
        # there is no separate custom-category entrance.
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u6062\u590d\u8bc4\u5206")
        _select(browser, "[name=category_id]", "extension")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        catalog = _json_get(browser, "/api/data-modules/product-catalog")
        recovery_module = next(item for item in catalog["modules"] if item["label"] == "\u6062\u590d\u8bc4\u5206")
        assert recovery_module["category_id"] == "extension" and recovery_module["display_surface"] == "page_widget" and recovery_module["actual_unit"] == "" and recovery_module["data_type"] == "number", recovery_module
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('home')")
        _wait(browser, "!!document.querySelector('.dm-page-widget-strip')")
        assert browser.evaluate("document.body.innerText.includes('恢复评分')")
        # The same page-widget path also works for Movement and for a unitless metric.
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools',{panel:'data-modules'})")
        _wait(browser, "!!document.querySelector('.dm-management-page')")
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u52a8\u4f5c\u51c6\u5907\u5ea6")
        _select(browser, "[name=category_id]", "movement")
        _select(browser, "[name=display_surface]", "page_widget")
        _select(browser, "[name=display_page]", "movement")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        movement_module = next(item for item in _json_get(browser, "/api/data-modules/product-catalog")["modules"] if item["label"] == "\u52a8\u4f5c\u51c6\u5907\u5ea6")
        assert movement_module["display_page"] == "movement" and movement_module["actual_unit"] == "" and movement_module["data_type"] == "number", movement_module
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('movements')")
        _wait(browser, "!!document.querySelector('.dm-page-widget-strip')")
        assert browser.evaluate("document.body.innerText.includes('动作准备度')")
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools',{panel:'data-modules'})")
        _wait(browser, "!!document.querySelector('.dm-management-page')")

        # Alias collision is human-facing and never shows a JSON error block.
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u91cd\u590d\u522b\u540d")
        _set_css(browser, "[name=actual_unit]", "bpm")
        _set_css(browser, "[name=aliases]", "\u6668\u95f4\u8109\u640f")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!!document.querySelector('[data-dm-form-error]:not([hidden])')")
        error_text = browser.evaluate("document.querySelector('[data-dm-form-error]').textContent")
        assert "已经用于" in error_text and "MODULE_" not in error_text, error_text
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.root.innerHTML=''")

        # Edit keeps the stable module id while moving presentation.
        _click_dataset(browser, "[data-dm-edit]", "dmEdit", temperature_id)
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u65e5\u95f4\u4f53\u6e29\uff08\u5c45\u5bb6\uff09")
        _set_css(browser, "[name=aliases]", "\u65e5\u95f4\u4f53\u6e29\uff08\u5c45\u5bb6\uff09,day temperature")
        _select(browser, "[name=placement]", "detail")
        _set_checked(browser, "[name=statistics_visible]", True)
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        edited = next(item for item in _json_get(browser, "/api/data-modules/product-catalog")["modules"] if item["module_id"] == temperature_id)
        assert edited["label"] == "\u65e5\u95f4\u4f53\u6e29\uff08\u5c45\u5bb6\uff09" and edited["placement"] == "detail" and edited["capabilities"]["statistics_visible"] is True
        for raw in ("2026-08-10 \u65e5\u95f4\u4f53\u6e29\uff08\u5c45\u5bb6\uff09 36.5 C", "2026-08-12 \u65e5\u95f4\u4f53\u6e29\uff08\u5c45\u5bb6\uff09 36.8 C"):
            temperature_preview = _json_post(browser, "/api/data-modules/preview", {"raw": raw})
            assert temperature_preview["status"] == 200, temperature_preview
            assert _json_post(browser, "/api/data-modules/save", {"preview": temperature_preview["body"], "confirmed": True})["status"] == 200
        _wait(browser, "!!document.querySelector('[data-dm-statistics]')")
        _click_dataset(browser, "[data-dm-statistics]", "dmStatistics", temperature_id)
        _wait(browser, "!!document.querySelector('.dm-stat-chart')")
        stats_text = browser.evaluate("document.querySelector('.dm-module-statistics').innerText")
        assert "最新" in stats_text and "平均" in stats_text and "变化" in stats_text, stats_text
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.root.innerHTML='' ")

        # Capability is opt-in and remains local-only.
        recovery_id = next(item["module_id"] for item in _json_get(browser, "/api/data-modules/product-catalog")["modules"] if item["label"] == "\u6062\u590d\u8bc4\u5206")
        _click_dataset(browser, "[data-dm-edit]", "dmEdit", recovery_id)
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_checked(browser, "[name=analysis_visible]", True)
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        enabled = next(item for item in _json_get(browser, "/api/data-modules/product-catalog")["modules"] if item["module_id"] == recovery_id)
        assert enabled["capabilities"]["analysis_visible"] is True
        cloud_dry_run = _json_get(browser, "/api/data-modules/cloud-dry-run")
        assert cloud_dry_run["meta"]["network_request_made"] is False

        # Delete removes the candidate definition and its candidate history.
        _click(browser, "[data-dm-new-module]")
        _wait(browser, "!!document.querySelector('#dm-definition-form')")
        _set_css(browser, "[name=label]", "\u5220\u9664\u793a\u4f8b")
        _select(browser, "[name=category_id]", "extension")
        _set_css(browser, "[name=aliases]", "\u5220\u9664\u793a\u4f8b")
        _click(browser, "[data-dm-submit-definition]")
        _wait(browser, "!document.querySelector('#dm-definition-form')")
        delete_module_id = next(item["module_id"] for item in _json_get(browser, "/api/data-modules/product-catalog")["modules"] if item["label"] == "\u5220\u9664\u793a\u4f8b")
        record_preview = _json_post(browser, "/api/data-modules/preview", {"raw": "2026-08-12 \u5220\u9664\u793a\u4f8b 3"})
        assert record_preview["status"] == 200
        record_saved = _json_post(browser, "/api/data-modules/save", {"preview": record_preview["body"], "confirmed": True})
        assert record_saved["status"] == 200
        browser.evaluate("window.confirm=()=>true")
        _click_dataset(browser, "[data-dm-delete]", "dmDelete", delete_module_id)
        _wait(browser, f"(async()=>!((await (await fetch('/api/data-modules/product-catalog')).json()).modules.some(item=>item.module_id==={json.dumps(delete_module_id)})))()")
        assert not any(item.get("module_id") == delete_module_id for item in _json_get(browser, "/api/data-modules/export")["records"])

        # A custom category has no standalone creation entrance, but an existing
        # custom category can still be removed from the management surface.
        category_create = _json_post(browser, "/api/data-modules/product-definition-preview", {"kind": "category", "action": "create", "values": {"category_id": "delete_review_category", "label": "\u5f85\u5220\u9664\u7c7b\u522b"}})
        assert category_create["status"] == 200
        _json_post(browser, "/api/data-modules/definition-save", {"preview": category_create["body"], "confirmed": True})
        browser.evaluate("location.reload()")
        _wait(browser, "window.__fitnessLedgerFormalMirrorReady===true && !!document.querySelector('.dm-management-page')")
        browser.evaluate("window.confirm=()=>true")
        _click_dataset(browser, "[data-dm-category-delete]", "dmCategoryDelete", "delete_review_category")
        _wait(browser, f"(async()=>!((await (await fetch('/api/data-modules/product-catalog')).json()).categories.some(item=>item.category_id==='delete_review_category')))()")

        # Retire the recorded pulse, retain history, and block new writes.
        _click_dataset(browser, "[data-dm-toggle]", "dmToggle", pulse_id)
        _wait(browser, f"(async()=>((await (await fetch('/api/data-modules/product-catalog')).json()).modules.find(item=>item.module_id==={json.dumps(pulse_id)}).status==='retired'))()")
        blocked = _json_post(browser, "/api/data-modules/preview", {"raw": "\u4eca\u5929\u6668\u95f4\u8109\u640f 59"})
        assert blocked["status"] == 400 and blocked["body"]["code"] == "MODULE_NOT_RECORDABLE", blocked
        pulse_history = _json_get(browser, f"/api/data-modules/history?module_id={urllib.parse.quote(pulse_id)}")
        assert len(pulse_history["history"]) == 1
        _click_dataset(browser, "[data-dm-toggle]", "dmToggle", pulse_id)
        _wait(browser, f"(async()=>((await (await fetch('/api/data-modules/product-catalog')).json()).modules.find(item=>item.module_id==={json.dumps(pulse_id)}).status==='active'))()")

        export_payload = _json_get(browser, "/api/data-modules/export")
        import_payload = dict(export_payload)
        import_payload["modules"] = [*import_payload["modules"], {"module_id": "unknown_import_metric", "label": "外部未知指标", "category_id": "body"}]
        import_preview = _json_post(browser, "/api/data-modules/import-preview", {"payload": import_payload})
        assert import_preview["status"] == 200 and not import_preview["body"]["write_attempted"] and import_preview["body"]["unknown_modules"], import_preview
        analysis_catalog = _json_get(browser, "/api/data-modules/analysis-catalog")
        assert len(export_payload["records"]) >= 1
        assert analysis_catalog.get("protocol_change_required_for_public_field") is True

        # Basic route and density smoke at desktop and narrow widths.
        for route, marker in [("quick", "#raw-entry"), ("body", ".archive-heading"), ("tools", ".dm-tools-entry")]:
            browser.evaluate(f"window.__fitnessLedgerFormalMirrorBridge.navigate({json.dumps(route)})")
            _wait(browser, f"!!document.querySelector({json.dumps(marker)})")
            metrics = browser.evaluate("({width:document.documentElement.scrollWidth,viewport:window.innerWidth,undefinedText:document.body.innerText.includes('undefined'),jsonText:document.body.innerText.includes('MODULE_ALIAS_CONFLICT')})")
            assert metrics["width"] <= metrics["viewport"] + 2 and not metrics["undefinedText"] and not metrics["jsonText"], metrics
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('tools',{panel:'data-modules'})")
        _wait(browser, "!!document.querySelector('.dm-review-hub') && document.querySelectorAll('[data-review-route]').length === 8")
        hub_routes = browser.evaluate("[...document.querySelectorAll('[data-review-route]')].map(item=>item.dataset.reviewRoute)")
        assert hub_routes == ["quick", "body", "diet", "training", "export", "sync", "health", "readiness"], hub_routes
        _click(browser, "[data-review-route='quick']")
        _wait(browser, "location.hash === '#quick' && !!document.querySelector('#raw-entry')")
        _command(browser, "Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('body')")
        _wait(browser, "!!document.querySelector('.archive-heading')")
        mobile_metrics = browser.evaluate("({width:document.documentElement.scrollWidth,viewport:window.innerWidth})")
        assert mobile_metrics["width"] <= mobile_metrics["viewport"] + 2, mobile_metrics

        # Restart the mirror against the same sandbox and verify definitions + history.
        browser.close();browser=None
        _close_process(edge);edge=None
        if edge_data:edge_data.cleanup();edge_data=None
        _close_process(service);service=None
        service=_start_service(port,sandbox.name)
        edge,browser,edge_data=_start_browser(port)
        restarted_catalog=_json_get(browser,"/api/data-modules/product-catalog")
        assert any(item["module_id"]==pulse_id for item in restarted_catalog["modules"])
        restarted_history=_json_get(browser,f"/api/data-modules/history?module_id={urllib.parse.quote(pulse_id)}")
        assert len(restarted_history["history"])==1

        print(json.dumps({
            "status":"PASS",
            "browser":"Microsoft Edge headless",
            "real_page":f"http://127.0.0.1:{port}/",
            "preview_zero_write":True,
            "confirm_history":True,
            "detail_zone":True,
            "unclassified_uses_existing_extension_category":True,
            "movement_page_widget":True,
            "delete_module_and_category":True,
            "alias_collision_human_error":True,
            "stable_id_edit":True,
            "retire_history_reenable":True,
            "restart_persistence":True,
            "normal_export_records":len(export_payload["records"]),
            "analysis_protocol_unchanged":True,
            "cloud_network_request_made":cloud_dry_run["meta"]["network_request_made"],
            "screenshot":str(screenshot_path),
        },ensure_ascii=False,indent=2))
    finally:
        if browser is not None:
            browser.close()
        _close_process(edge)
        _safe_cleanup(edge_data)
        _close_process(service)
        sandbox.cleanup()


if __name__ == "__main__":
    main()
