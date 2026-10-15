"""Actual PWA entry: daily archive -> exact session -> daily archive."""
from __future__ import annotations

import sys
import argparse
import threading
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = None
sys.path.insert(0, str(ROOT))

from mobile_viewer.app import create_app, _pwa_session_theme_names
from pwa_session_semantics_test import FakeAccess
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from web_desktop.backend.server import LedgerWebService, create_server
from fitness_ledger_core.shared_view_models import LedgerViewModels


def web_display():
    tracker = {"training_sessions": [{"id": "web-session", "Date": "2099-01-01", "session_theme_id": "custom",
                "session_theme_ids": ["custom"], "session_theme_name": "出差训练", "Split": "出差训练", "movement_items": [
                    {"id": "web-history", "movement_id": "M1", "display_name": "Recorded movement", "training_session_id": "web-session",
                     "date": "2099-01-01", "order": 1, "sets": [{"weight": 10, "reps": 8, "sets": 3}], "exclude_from_progress": True}]}]}
    service = LedgerWebService.__new__(LedgerWebService)
    service.data = SimpleNamespace(_tracker=lambda: tracker, get_record_detail=lambda day: {
        "date": day, "training": [{"split": "出差训练", "movements": [{"display_name": "Recorded movement", "sets": [], "exclude_from_progress": True}]}]})
    service.views = LedgerViewModels.__new__(LedgerViewModels)
    service.views.snapshot = lambda: (tracker, {"movements": []})
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            page.on("pageerror", lambda error: print("WEB_PAGE_ERROR", str(error)))
            def route_api(route):
                action = route.request.url.split("/api/", 1)[1]
                if action.startswith(("training?", "record?")):
                    route.continue_()
                elif action == "training-organization":
                    route.fulfill(json={"session_themes": [{"theme_id": "custom", "display_name": "出差训练", "active": True},
                        {"theme_id": "en", "display_name": "Travel Circuit", "active": True}, {"theme_id": "push", "display_name": "Push", "active": True}]})
                else:
                    route.fulfill(json=[] if action.startswith(("recent", "dictionary")) else {})
            page.route("**/api/**", route_api)
            page.goto(f"http://127.0.0.1:{server.server_port}/#training")
            page.wait_for_selector('.training-movement-row-shell.is-excluded')
            assert "否" in page.locator('.archive-progress-toggle').inner_text()
            assert "ENGLISH NAME NEEDED" not in page.locator('main').inner_text()
            assert "中文名称待补充" not in page.locator('main').inner_text()
            assert "Travel Circuit" in page.locator('main').inner_text()
            page.locator('.body-theme-control[data-training-theme="custom"]').click()
            page.wait_for_function("() => document.querySelector('.training-theme-header h1')?.textContent.includes('出差训练')")
            page.locator('.session button[data-detail]').evaluate('(el)=>el.click()')
            try:
                page.wait_for_selector('.modal .training-progress-field', timeout=5000)
            except Exception:
                print("WEB_DETAIL_DIAGNOSTIC", page.locator('.modal').all_text_contents(), page.locator('#toast').inner_text())
                raise
            assert "否" in page.locator('.modal .training-progress-field').inner_text()
            page.locator('.modal [data-close]').evaluate('(el)=>el.click()')
            page.evaluate("() => {localStorage.setItem('fitness-ledger.ui-language.v1','en'); location.reload()}")
            page.wait_for_selector('.training-theme-page')
            page.locator('.body-theme-control[data-training-theme="custom"]').click()
            page.wait_for_function("() => document.querySelector('.training-theme-header h1')?.textContent.includes('出差训练')")
            assert "Count toward progress: No" in page.locator('.archive-progress-toggle').inner_text()
            page.locator('.session button[data-detail]').evaluate('(el)=>el.click()')
            page.wait_for_selector('.modal .training-progress-field')
            assert "No" in page.locator('.modal .training-progress-field').inner_text()
            if OUTPUT:
                page.locator('.modal .training-progress-field').scroll_into_view_if_needed()
                page.screenshot(path=str(OUTPUT / "web-detail-en.png"))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


class DisplayAccess(FakeAccess):
    def __init__(self):
        super().__init__()
        self.tracker_file = Path(__file__).parent / "missing-fixture-data" / "tracker.json"
        self._sessions[0]["movement_items"][0]["exclude_from_progress"] = True
        self._sessions[0]["session_theme_ids"] = ["custom-theme"]
        self._sessions[0]["session_theme_name"] = "出差训练"
        self._sessions[0]["Split"] = "出差训练"
        self._sessions[1]["session_theme_ids"] = ["custom-en"]
        self._sessions[1]["session_theme_name"] = "Travel Circuit"
        self._sessions[1]["Split"] = "Travel Circuit"

    def get_record_detail(self, entry_date):
        return {"date": entry_date, "body": {}, "diet": {}, "training": [
            {"training_session_id": row["id"], "date": row["Date"],
             "split": row["Split"], "standardized_summary": row["Standardized Summary"]}
            for row in self._sessions
        ]}


def main():
    access = DisplayAccess()
    app = create_app(access)
    client = app.test_client()
    detail = client.get("/api/pwa/read?action=trainingDayDetail&sessionId=same-day-1").get_json()["data"]
    assert detail["movements"][1]["exclude_from_progress"] is True
    assert detail["movements"][0]["exclude_from_progress"] is False
    assert detail["session"]["theme_names"] == ["出差训练"]
    organization = {"session_themes": [{"theme_id": "x", "display_name": "Renamed", "active": False}]}
    assert _pwa_session_theme_names({"session_theme_id": "x", "session_theme_name": "Old"}, organization) == ["Renamed"]
    assert _pwa_session_theme_names({"Split": "Travel Circuit"}, {}) == ["Travel Circuit"]
    assert _pwa_session_theme_names({"theme_names": ["Cloud Name"]}, {}) == ["Cloud Name"]
    assert _pwa_session_theme_names({"session_theme_ids": ["x", "new"], "theme_names": ["Renamed", "New Custom"]}, organization) == ["Renamed", "New Custom"]
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(viewport={"width": 390, "height": 844}, service_workers="block")
            page = context.new_page()
            errors = []
            http_errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: http_errors.append(response.url) if response.status >= 500 else None)
            base = f"http://127.0.0.1:{server.server_port}/pwa/"
            page.goto(base + "#record?date=2026-09-10&from=body")
            page.wait_for_selector('[data-action="daily-session"]')
            assert page.locator('[data-action="daily-session"]').count() == 2
            if OUTPUT:
                page.screenshot(path=str(OUTPUT / "pwa-daily.png"))
            for index, session_id in enumerate(("same-day-1", "same-day-2")):
                page.locator('[data-action="daily-session"]').nth(index).click()
                page.wait_for_function("id => location.hash.includes(`sessionId=${id}`)", arg=session_id)
                page.wait_for_selector(".training-session-only")
                assert ("出差训练" if index == 0 else "Travel Circuit") in page.locator(".session-theme-summary").inner_text()
                if index == 0:
                    assert page.locator(".session-movement-card").count() == 2
                    assert "否" in page.locator(".training-progress-field").nth(1).inner_text()
                    if OUTPUT:
                        page.wait_for_timeout(700)
                        page.screenshot(path=str(OUTPUT / "pwa-session.png"), full_page=True)
                else:
                    assert page.locator(".session-movement-card").count() == 0
                page.locator('[data-action="route-back"]').click()
                page.wait_for_selector('[data-action="daily-session"]')
                assert "mode=training" not in page.url and "from=body" in page.url
            # Cloud daily records use id/_id rather than training_session_id.
            def cloud_daily(route):
                route.fulfill(json={"ok": True, "data": {"date": "2026-09-10", "body": [], "diet": [],
                    "training": [{"_id": "same-day-2", "Date": "2026-09-10", "Split": "Travel Circuit"}]}})
            page.route("**/api/pwa/read?action=recordDetail*", cloud_daily)
            page.reload()
            page.wait_for_selector('[data-action="daily-session"]')
            page.locator('[data-action="daily-session"]').click()
            page.wait_for_selector(".training-session-only")
            assert "sessionId=same-day-2" in page.url
            assert "Travel Circuit" in page.locator(".session-theme-summary").inner_text()
            assert not errors, errors
            assert not http_errors, http_errors
            browser.close()
        web_display()
        print("TRAINING_DISPLAY_BROWSER_OK: exact sessions, back route, Web bilingual custom names, exclusion fields")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    OUTPUT = parser.parse_args().output
    if OUTPUT:
        OUTPUT.mkdir(parents=True, exist_ok=True)
    main()
