from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from tools.movement_lifecycle_core_test import SOURCE_ID, TARGET_ID, lifecycle_values  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def post_json(base: str, path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def get_json(base: str, path: str) -> tuple[int, object]:
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def browser_contract() -> None:
    edge = next((path for path in (
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    ) if path.is_file()), None)
    if edge is None:
        return
    index = (PROJECT / "web_desktop/frontend/index.html").read_text(encoding="utf-8")
    app = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    harness = """
window.fetch=async path=>({ok:true,status:200,json:async()=>String(path).includes('dictionary')?[
  {movement_id:'BACK_002',display_name:'坐姿划船',english_name:'Seated Row',aliases:[],muscle_group:'Back',active:true,history_count:2,exclude_from_progress:false},
  {movement_id:'BACK_001',display_name:'高位下拉',english_name:'Lat Pulldown',aliases:[],muscle_group:'Back',active:true,history_count:1}
]:[]});
state.dictionary=[
  {movement_id:'BACK_002',display_name:'坐姿划船',english_name:'Seated Row',aliases:[],muscle_group:'Back',active:true,history_count:2,exclude_from_progress:false},
  {movement_id:'BACK_001',display_name:'高位下拉',english_name:'Lat Pulldown',aliases:[],muscle_group:'Back',active:true,history_count:1}
];
await new Promise(resolve=>setTimeout(resolve,120));
openDictionaryEditor('BACK_002');
const editor=document.querySelector('[data-movement-merge-open]');
const progressToggle=!!document.querySelector('[data-movement-progress-exclusion]');
editor?.click();
await new Promise(resolve=>setTimeout(resolve,120));
const report=document.createElement('div');report.id='lifecycle-ui-browser-report';
report.dataset.value=encodeURIComponent(JSON.stringify({
  mergeAction:!!editor,
  progressToggle,
  modalTitle:document.querySelector('#movement-merge-title')?.textContent,
  candidateCount:document.querySelectorAll('[data-custom-merge-target]').length
}));document.body.appendChild(report);
"""
    script = '<script type="module" src="app.js"></script>'
    assert index.count(script) == 1
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-lifecycle-browser-") as temp:
        page = Path(temp) / "index.html"
        page.write_text(index.replace(script, f'<script type="module">{app}\n{harness}</script>'), encoding="utf-8")
        output = subprocess.run(
            [str(edge), "--headless=new", "--disable-gpu", "--virtual-time-budget=3000", "--dump-dom", page.as_uri()],
            check=True, capture_output=True, text=True, encoding="utf-8", timeout=20,
        ).stdout
    match = re.search(r'id="lifecycle-ui-browser-report" data-value="([^"]+)"', output)
    assert match, "Browser lifecycle report was not rendered."
    from urllib.parse import unquote
    report = json.loads(unquote(match.group(1)))
    assert report["mergeAction"] and report["progressToggle"]
    assert report["modalTitle"] == "合并到其他动作", report


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-lifecycle-ui-") as temp:
        root = Path(temp)
        tracker, dictionary = lifecycle_values()
        tracker_path, dictionary_path = root / "tracker.json", root / "movement_dictionary.json"
        write_json(tracker_path, tracker)
        write_json(dictionary_path, dictionary)
        service = LedgerWebService(tracker_path, dictionary_path, root / "backups")
        server = create_server(port=0, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            status, candidates = get_json(
                base,
                "/api/movements/merge-candidates?" + urllib.parse.urlencode({"source_id": SOURCE_ID}),
            )
            candidate_ids = {item["movement_id"] for item in candidates}
            assert status == 200 and TARGET_ID in candidate_ids
            assert SOURCE_ID not in candidate_ids
            assert all(not item["movement_id"].startswith("CUSTOM_") for item in candidates)

            status, preview = post_json(
                base, "/api/movements/merge/preview", {"source_id": SOURCE_ID, "target_id": TARGET_ID}
            )
            assert status == 200 and preview["can_execute"] and preview["plan_identity"]
            assert preview["history"]["source_history_count"] == 2
            status, result = post_json(
                base,
                "/api/movements/merge/execute",
                {"source_id": SOURCE_ID, "target_id": TARGET_ID, "plan_identity": preview["plan_identity"]},
            )
            assert status == 200 and result["status"] == "UPDATED" and result["target_id"] == TARGET_ID
            ids_after_merge = {item["movement_id"] for item in service.dictionary_entries()}
            assert SOURCE_ID not in ids_after_merge and TARGET_ID in ids_after_merge

            status, excluded = post_json(
                base, "/api/movements/progress-exclusion", {"movement_id": TARGET_ID, "excluded": True}
            )
            assert status == 200 and excluded["status"] == "UPDATED" and excluded["exclude_from_progress"] is True
            assert TARGET_ID not in {item["movement_id"] for item in service.commands.movement_progress_definitions()}
            assert TARGET_ID in {item["movement_id"] for item in service.dictionary_entries()}
            status, stable = post_json(
                base, "/api/movements/progress-exclusion", {"movement_id": TARGET_ID, "excluded": True}
            )
            assert status == 200 and stable["status"] == "NO_CHANGES"
            status, restored = post_json(
                base, "/api/movements/progress-exclusion", {"movement_id": TARGET_ID, "excluded": False}
            )
            assert status == 200 and restored["status"] == "UPDATED"
            assert TARGET_ID in {item["movement_id"] for item in service.commands.movement_progress_definitions()}
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    app = PROJECT / "web_desktop" / "frontend" / "app.js"
    js = app.read_text(encoding="utf-8")
    assert "data-movement-merge-open" in js
    assert "/api/movements/merge/preview" in js and "/api/movements/merge/execute" in js
    assert "data-movement-progress-exclusion" in js
    assert "/api/movements/progress-exclusion" in js
    assert "data-custom-merge-open" in js and "/api/movements/custom-merge/preview" in js
    browser_contract()
    print("FITNESS_LEDGER_MOVEMENT_LIFECYCLE_UI_OK")


if __name__ == "__main__":
    main()
