"""Exercise export guidance and downloaded artifacts in isolated headless Edge."""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.archive_navigation_test import fixture
from tools.run_data_module_formal_mirror import ensure_sandbox
from tools.data_module_formal_mirror_browser_e2e_test import (
    _click, _close_process, _safe_cleanup, _set_checked, _set_css,
    _start_browser, _wait,
)
from web_desktop.backend.server import LedgerWebService, create_server


def main() -> None:
    edge = browser = edge_data = server = None
    with tempfile.TemporaryDirectory(prefix="fl-export-conversation-") as temporary:
        root = Path(temporary)
        tracker, dictionary = fixture()
        # Bring the synthetic archive into the current seven-day window.
        serialized = json.dumps(tracker, ensure_ascii=False)
        for offset in range(5):
            serialized = serialized.replace(
                f"2026-07-{10 + offset:02}",
                (date.today() - timedelta(days=4 - offset)).isoformat(),
            )
        tracker = json.loads(serialized)
        tracker["daily_records"] = [{"Date": date.today().isoformat(), "Weight (kg)": 70}]
        tracker["diet_records"] = [{"Date": date.today().isoformat(), "Calories": 2000}]
        paths = [root / "tracker.json", root / "movement_dictionary.json"]
        for path, data in zip(paths, (tracker, dictionary)):
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        _, _, _, registry = ensure_sandbox(root)
        service = LedgerWebService(*paths, root / "backups", data_module_registry_file=registry)
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        server = create_server("127.0.0.1", 0, service)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            edge, browser, edge_data = _start_browser(server.server_port)
            browser.evaluate("location.hash='tools?panel=export'")
            _wait(browser, "!!document.querySelector('#analysis-export-language-help')")
            _click(browser, '[data-analysis-llm-init]')
            _wait(browser, "!!document.querySelector('[data-analysis-llm-copy]')")
            prompt = browser.evaluate("document.querySelector('.entry-template-prompt').textContent")
            assert 'filters 必填' in prompt and 'target_dataset_id' in prompt and '只有收到真实导出数据包后' in prompt
            _click(browser, '.modal [data-close]')
            _set_css(browser, "#analysis-export-natural-language", "提取过去一周的全部数据")
            _click(browser, "[data-analysis-export-natural-preview]")
            _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='scope'")
            scope = browser.evaluate("document.querySelector('#analysis-export-bundle-list').innerText")
            assert "饮食" in scope and "训练" in scope and "动作" in scope, scope
            _click(browser, "[data-analysis-export-next]")
            _wait(browser, "!!document.querySelector('#analysis-export-confirm')")
            _set_checked(browser, "#analysis-export-confirm", True)
            _click(browser, "[data-analysis-export-confirm]")
            _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='done'")
            artifacts = browser.evaluate("""(async()=>await Promise.all(
                [...document.querySelectorAll('.analysis-export-download-list a')].map(async a=>{
                    const response=await fetch(a.href); const text=await response.text();
                    return {status:response.status,format:new URL(a.href).searchParams.get('format'),text};
                })))()""")
            assert artifacts and all(item["status"] == 200 for item in artifacts), artifacts
            bundles = [json.loads(item["text"]) for item in artifacts if item["format"] == "json"]
            assert bundles and sum(len(item["records"]) for item in bundles) > 0
            types = {dataset["type"] for bundle in bundles for dataset in bundle["request"]["datasets"]}
            assert types == {"body", "diet", "training", "movement_progress"}, types
            for bundle in bundles:
                assert bundle["safety_flags"] == {
                    "raw_included": False, "executor_called": False, "formal_data_written": False,
                }
            _click(browser, "[data-analysis-export-back]")
            _set_css(browser, "#analysis-export-natural-language", "提取一些记录")
            _click(browser, "[data-analysis-export-natural-preview]")
            _wait(browser, "!!document.querySelector('#analysis-export-natural-result [data-analysis-export-prompt]')")
            _click(browser, "#analysis-export-natural-result [data-analysis-export-prompt]")
            assert browser.evaluate("document.querySelector('#analysis-export-natural-language').value") == "提取过去一周的全部数据。"
            assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths] == before
            print(json.dumps({"status": "PASS", "browser": "headless Edge", "datasets": sorted(types),
                              "artifacts_fetched": len(artifacts), "clarification_example": True,
                              "anonymous_ledger_unchanged": True}, ensure_ascii=False))
        finally:
            if browser is not None:
                browser.close()
            _close_process(edge)
            _safe_cleanup(edge_data)
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
