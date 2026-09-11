"""Browser evidence for complex-set Review and Session-theme/superset surfaces."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from data_module_formal_mirror_browser_e2e_test import (
    DevToolsSocket,
    _close_process,
    _command,
    _edge_path,
    _free_port,
    _safe_cleanup,
    _start_browser,
    _start_service,
    _wait,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(r"C:\Users\26087\.codex\visualizations\2026\09\11\01a08fdf-80a7-7d82-9c93-1585913987bf")
RAW = """2099-01-06
training: 胸肩
1. Incline Press
(7.5+5)-(6+8)-3
2. Triceps Pushdown
30kg x 12 x 3
superset: A = movement 1, movement 2
"""


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_fixture(root: Path) -> None:
    session_id = "session-complex-superset"
    write_json(root / "tracker.json", {
        "daily_records": [],
        "diet_records": [],
        "raw_entries": [],
        "movements": {},
        "training_organization": {
            "session_themes": [
                {"theme_id": "chest", "display_name": "胸", "aliases": ["胸部"], "active": True, "sort_order": 10},
                {"theme_id": "shoulders", "display_name": "肩", "aliases": ["肩部"], "active": True, "sort_order": 20},
            ],
            "movement_categories": [],
        },
        "training_sessions": [{
            "id": session_id,
            "No.": 1,
            "Date": "2099-01-05",
            "Split": "胸肩",
            "session_theme_name": "胸肩",
            "session_theme_ids": ["chest", "shoulders"],
            "Raw Record": RAW,
            "Standardized Summary": "第1个动作：Incline Press；第2个动作：Triceps Pushdown",
            "Notes": "匿名浏览器证据 fixture",
            "organization_relations": [{
                "id": f"superset:{session_id}:A",
                "type": "superset",
                "label": "A",
                "members": ["mi-press", "mi-pushdown"],
            }],
            "movement_items": [
                {
                    "id": "mi-press", "movement_instance_id": "mi-press", "movement_id": "m_press",
                    "display_name": "Incline Press", "date": "2099-01-05", "training_day": 1,
                    "order": 1, "order_in_session": 1, "sets": [{
                        "segments": [{"weight": 7.5, "reps": 6}, {"weight": 5, "reps": 8}], "sets": 3,
                    }], "training_session_id": session_id, "notes": "",
                },
                {
                    "id": "mi-pushdown", "movement_instance_id": "mi-pushdown", "movement_id": "m_pushdown",
                    "display_name": "Triceps Pushdown", "date": "2099-01-05", "training_day": 1,
                    "order": 2, "order_in_session": 2, "sets": [{"weight": 30, "reps": 12, "sets": 3}],
                    "training_session_id": session_id, "notes": "",
                },
            ],
        }],
    })
    write_json(root / "movement_dictionary.json", {
        "version": "1.0",
        "movements": [
            {"movement_id": "m_press", "display_name": "Incline Press", "english_name": "Incline Press", "aliases": ["Incline Press"], "muscle_group": "Chest", "active": True},
            {"movement_id": "m_pushdown", "display_name": "Triceps Pushdown", "english_name": "Triceps Pushdown", "aliases": ["Triceps Pushdown"], "muscle_group": "Arms", "active": True},
        ],
    })


def set_text(browser: DevToolsSocket, selector: str, value: str) -> None:
    expression = f"""(() => {{
      const element=document.querySelector({json.dumps(selector)});
      if(!element)return false;
      element.value={json.dumps(value, ensure_ascii=False)};
      element.dispatchEvent(new Event('input',{{bubbles:true}}));
      element.dispatchEvent(new Event('change',{{bubbles:true}}));
      return true;
    }})()"""
    assert browser.evaluate(expression) is True, selector


def click(browser: DevToolsSocket, selector: str) -> None:
    expression = f"""(() => {{
      const element=document.querySelector({json.dumps(selector)});
      if(!element)return false;element.click();return true;
    }})()"""
    assert browser.evaluate(expression) is True, selector


def capture(browser: DevToolsSocket, path: Path) -> None:
    result = _command(browser, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(result["data"]))


def post_json(browser: DevToolsSocket, path: str, payload: dict) -> dict:
    result = browser.evaluate(f"""(async()=>{{
      const response=await fetch({json.dumps(path)},{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({json.dumps(payload,ensure_ascii=False)})}});
      return await response.json();
    }})()""")
    assert isinstance(result, dict), result
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    sandbox = tempfile.TemporaryDirectory(prefix="fitness-ledger-complex-superset-browser-")
    root = Path(sandbox.name)
    write_fixture(root)
    port = _free_port()
    service = None
    edge = None
    browser = None
    edge_data = None
    try:
        service = _start_service(port, sandbox.name)
        edge, browser, edge_data = _start_browser(port)
        _command(browser, "Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1100, "deviceScaleFactor": 1, "mobile": False})

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('quick'); true")
        _wait(browser, "!!document.querySelector('#raw-entry')")
        browser.evaluate("document.querySelector('#entry-input-mode').value='standard'; true")
        set_text(browser, "#raw-entry", RAW)
        click(browser, "#parse")
        _wait(browser, "!!document.querySelector('.review-scroll-page')")
        review_text = browser.evaluate("document.body.innerText")
        assert "超级组 A" in review_text and "7.5kg × 6 + 5kg × 8 × 3组" in review_text, review_text[:2000]
        capture(browser, output / "complex-set-review.png")

        parsed = post_json(browser, "/api/parse", {"raw": RAW})
        saved = post_json(browser, "/api/save", {"review_id": parsed["review_id"], "review": parsed["review"]})
        assert saved["ok"] is True, saved

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('training'); true")
        _wait(browser, "!!document.querySelector('.training-theme-page')")
        _wait(browser, "document.querySelectorAll('.body-theme-control').length >= 2")
        click(browser, "[data-training-theme='chest']")
        _wait(browser, "document.querySelectorAll('.session-slip').length === 1")
        chest_text = browser.evaluate("document.body.innerText")
        assert "Incline Press" in chest_text and "Triceps Pushdown" in chest_text and "超级组 A" in chest_text, chest_text[:2500]
        capture(browser, output / "superset-session-chest-theme.png")
        click(browser, "[data-training-theme='shoulders']")
        _wait(browser, "document.querySelectorAll('.session-slip').length === 1")
        shoulder_text = browser.evaluate("document.body.innerText")
        assert "Incline Press" in shoulder_text and "Triceps Pushdown" in shoulder_text, shoulder_text[:2500]
        capture(browser, output / "superset-session-shoulders-theme.png")

        browser.evaluate("window.__fitnessLedgerFormalMirrorBridge.navigate('movements'); true")
        _wait(browser, "!!document.querySelector('[data-select-movement-id=\\\"m_press\\\"]')")
        click(browser, "[data-select-movement-id='m_press']")
        _wait(browser, "!!document.querySelector('.movement-detail-page .trajectory')")
        history_text = browser.evaluate("document.body.innerText")
        assert "7.5kg × 6 + 5kg × 8 × 3组" in history_text and "超级组 A" in history_text and "Triceps Pushdown" in history_text, history_text[:2500]
        capture(browser, output / "complex-set-history-and-superset-context.png")

        print(json.dumps({
            "status": "PASS",
            "browser": "Microsoft Edge headless",
            "review": str(output / "complex-set-review.png"),
            "superset_session": str(output / "superset-session-chest-theme.png"),
            "superset_session_shoulders": str(output / "superset-session-shoulders-theme.png"),
            "movement_history": str(output / "complex-set-history-and-superset-context.png"),
            "multi_theme": {"chest_sessions": 1, "shoulder_sessions": 1},
            "complex_set_text": "7.5kg × 6 + 5kg × 8 × 3组",
            "relation_text": "超级组 A · Triceps Pushdown",
        }, ensure_ascii=False, indent=2))
    finally:
        if browser is not None:
            browser.close()
        _close_process(edge)
        _close_process(service)
        _safe_cleanup(edge_data)
        sandbox.cleanup()


if __name__ == "__main__":
    main()
