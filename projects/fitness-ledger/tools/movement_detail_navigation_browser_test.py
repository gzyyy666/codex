from __future__ import annotations

import tempfile
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from movement_progress_chart_review_server import review_fixture, write_json
from web_desktop.backend.server import LedgerWebService, create_server


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-movement-route-test-") as temporary:
        root = Path(temporary)
        tracker, dictionary = review_fixture()
        tracker_path, dictionary_path = root / "tracker.json", root / "movement_dictionary.json"
        write_json(tracker_path, tracker)
        write_json(dictionary_path, dictionary)
        service = LedgerWebService(
            tracker_path,
            dictionary_path,
            root / "backups",
            build_info_override={
                "mode": "ANONYMOUS MOVEMENT NAVIGATION TEST",
                "status": "PREVIEW",
                "formal_data_used": False,
                "cloud_mutation": False,
                "mini_publish": False,
            },
        )
        server = create_server("127.0.0.1", 0, service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}/"
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 620})
                page.set_default_timeout(10_000)

                # Movement Progress chart remains interactive and its point opens
                # the matching training session; the chart tooltip exposes both metrics.
                page.goto(base + "#movements", wait_until="domcontentloaded")
                movement_tile = page.locator('[data-select-movement-id="REVIEW_INCLINE_PRESS"]').first
                movement_tile.wait_for()
                movement_tile.click()
                page.locator(".movement-detail-page").wait_for()
                hit = page.locator(".chart-hit-zone").first
                hit.wait_for()
                hit.hover()
                tooltip = page.locator(".movement-chart-tooltip")
                tooltip.wait_for(state="visible")
                tip = tooltip.inner_text()
                assert "7.5" in tip and "255" in tip, tip

                # The recorded-history timeline remains clickable too and opens
                # the corresponding date rather than being covered by the route UI.
                page.locator(".trajectory .history-date-link").first.click()
                page.wait_for_url("**/#training**")
                assert "date=2026-09-14" in page.url, page.url
                page.go_back()
                page.locator(".chart-hit-zone").first.wait_for()
                hit.click()
                page.wait_for_url("**/#training**")
                chart_training_url = page.url

                # Enter the same movement from Training and use the visible
                # global route-back control. It must restore the exact parent URL.
                training_row = page.locator(
                    '[data-movement-source="training"][data-select-movement-id="REVIEW_INCLINE_PRESS"]'
                ).last
                training_row.wait_for()
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                parent_scroll = page.evaluate("window.scrollY")
                training_url = page.url
                training_row.evaluate("element => element.click()")
                page.locator(".movement-detail-page").wait_for()
                page.locator("[data-dm-route-back]").click()
                page.wait_for_url(training_url)
                page.locator(
                    '[data-movement-source="training"][data-select-movement-id="REVIEW_INCLINE_PRESS"]'
                ).first.wait_for()
                restored_scroll = page.evaluate("window.scrollY")
                assert abs(restored_scroll - parent_scroll) <= 2, (parent_scroll, restored_scroll)
                assert page.url == training_url

                # The chart-origin Training page is still one level below its
                # movement detail; browser-history return follows that real parent.
                page.go_back()
                page.locator(".movement-detail-page").wait_for()
                page.locator("[data-dm-route-back]").click()
                page.wait_for_url("**/#movements")
                assert "movement_id=" not in page.url

                # Opening from the index returns to the index; a direct deep link
                # without an in-app parent also falls back safely to that index.
                page.locator('[data-select-movement-id="REVIEW_INCLINE_PRESS"]').first.click()
                page.locator(".movement-detail-page").wait_for()
                page.locator("[data-dm-route-back]").click()
                page.wait_for_url("**/#movements")
                assert "movement_id=" not in page.url

                page.goto(base + "#movements?movement_id=REVIEW_INCLINE_PRESS", wait_until="domcontentloaded")
                page.locator("[data-dm-route-back]").wait_for()
                page.locator("[data-dm-route-back]").click()
                page.wait_for_url("**/#movements")
                assert "movement_id=" not in page.url

                browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    print("MOVEMENT_DETAIL_INTERACTION_AND_ORIGIN_RETURN_BROWSER_OK")


if __name__ == "__main__":
    main()
