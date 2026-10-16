"""Exercise archive HTTP reads and browser rendering beyond both old cutoffs."""
from __future__ import annotations

import copy
import json
import sys
import threading
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from fitness_ledger_core.shared_view_models import LedgerViewModels
from web_desktop.backend.server import LedgerWebService, create_server
from playwright.sync_api import sync_playwright


def main() -> None:
    rows = [{"Date": (date(2098, 1, 1) + timedelta(days=i)).isoformat(),
             "No.": i + 1, "id": f"session-{i}", "Split": "Back",
             "Weight (kg)": 70, "Notes": f"archive-{i}"} for i in range(250)]
    tracker = {key: copy.deepcopy(rows) for key in
               ("daily_records", "diet_records", "training_sessions")}
    service = LedgerWebService.__new__(LedgerWebService)
    service.data = SimpleNamespace(_tracker=lambda: copy.deepcopy(tracker))
    service.views = LedgerViewModels.__new__(LedgerViewModels)
    service.views.snapshot = lambda: (copy.deepcopy(tracker), {"movements": []})
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for collection in ("body", "diet", "training"):
            for limit, expected in ((0, 250), (100, 100), (200, 200), (1000, 200), (-1, 1)):
                with urlopen(f"{base}/api/{collection}?limit={limit}") as response:
                    result = json.load(response)
                assert len(result) == expected, (collection, limit, len(result))
                assert result[0]["Date"] == rows[-1]["Date"]
                if limit == 0:
                    assert result[-1]["Date"] == rows[0]["Date"]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page()
            requests = []
            def route_api(route):
                path = route.request.url.split("/api/", 1)[1]
                if path.split("?", 1)[0] in ("body", "diet", "training"):
                    requests.append(path)
                    route.continue_()
                else:
                    value = [] if path.startswith(("recent", "dictionary", "movements")) else {}
                    route.fulfill(json=value)
            page.route("**/api/**", route_api)
            page.goto(base)
            for collection, selector in (("body", ".body-slip"), ("diet", ".diet-slip"),
                                         ("training", ".session[data-training-date]")):
                page.evaluate("name => { location.hash = name }", collection)
                page.wait_for_function("([selector,count]) => document.querySelectorAll(selector).length === count",
                                       arg=[selector, 250])
                # Deferred offscreen cards must render when actually reached.
                page.locator(selector).last.scroll_into_view_if_needed()
                page.wait_for_function("([selector,day]) => document.querySelectorAll(selector)[249].innerText.includes(day)",
                                       arg=[selector, rows[0]["Date"]])
                assert rows[0]["Date"] in page.locator(selector).last.inner_text()
                page.locator(f"#{collection}-order").select_option("oldest")
                page.locator(selector).first.scroll_into_view_if_needed()
                page.wait_for_function("([selector,day]) => document.querySelector(selector).innerText.includes(day)",
                                       arg=[selector, rows[0]["Date"]])
                assert rows[0]["Date"] in page.locator(selector).first.inner_text()
                page.locator(f"#{collection}-search").fill(rows[0]["Date"])
                page.wait_for_function("selector => document.querySelectorAll(selector).length === 1", arg=selector)
                assert rows[0]["Date"] in page.locator(selector).inner_text()
            assert all(f"{name}?limit=0" in requests for name in ("body", "diet", "training")), requests
            browser.close()
        print("WEB_COMPLETE_HISTORY_OK: 250 records; HTTP limits, earliest dates, sorting and search verified")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
