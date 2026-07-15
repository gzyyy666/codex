from __future__ import annotations

import hashlib
import json
import os
import sys
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from fitness_ledger_core.data_quality_view import LOGGER, SilentHealthCheck, issue_key
from web_desktop.backend.server import LedgerWebService, create_server


class FakeApp:
    calls = 0

    def collect_data_issues(self) -> list[dict]:
        FakeApp.calls += 1
        return list(self.database.get("fixture_issues", []))


class FakeStable:
    FitnessTrackerApp = FakeApp

    @staticmethod
    def movement_definition_index(_dictionary: dict) -> tuple[dict, dict]:
        return {}, {}


def file_state(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


class FixtureData:
    @staticmethod
    def get_today_summary() -> dict:
        return {"date": "2026-07-15", "body": {}, "diet": {}, "training": {}}


class FixtureWebService:
    def __init__(self, health: dict) -> None:
        self.health = health
        self.data = FixtureData()

    def archive_health(self) -> dict:
        return self.health

    @staticmethod
    def recent(_limit: int) -> list:
        return []

    @staticmethod
    def collection(_name: str, _limit: int) -> list:
        return []

    @staticmethod
    def movement_index(_query: str, _limit: int) -> list:
        return []

    @staticmethod
    def dictionary_entries() -> list:
        return []

    @staticmethod
    def cloud_sync_status() -> dict:
        return {"sync_status": "NOT_CONFIGURED", "payload_stale": False}


def browser_dom(health: dict) -> str | None:
    candidates = (
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    )
    edge = next((path for path in candidates if path.is_file()), None)
    if edge is None:
        return None
    server = create_server(port=0, service=FixtureWebService(health))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [str(edge), "--headless=new", "--disable-gpu", "--virtual-time-budget=3000", "--dump-dom", f"http://127.0.0.1:{server.server_port}/"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        return result.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-silent-health-") as temp:
        root = Path(temp)
        tracker = root / "tracker.json"
        dictionary = root / "movement_dictionary.json"
        state_file = root / "data_check_state.json"
        write_json(tracker, {"fixture_issues": []})
        write_json(dictionary, {"movements": []})
        checker = SilentHealthCheck(tracker, dictionary, FakeStable, state_file)

        before = (file_state(tracker), file_state(dictionary), set(root.iterdir()))
        healthy = checker.summary()
        after = (file_state(tracker), file_state(dictionary), set(root.iterdir()))
        assert healthy["status"] == "OK" and healthy["issue_count"] == 0
        assert healthy["highest_severity"] is None and healthy["cached"] is False
        assert before == after

        calls = FakeApp.calls
        cached = checker.summary()
        assert cached["cached"] is True and FakeApp.calls == calls
        assert cached["data_fingerprint"] == healthy["data_fingerprint"]

        issues = [
            {"severity": "Low", "issue": "warning"},
            {"severity": "High", "issue": "error"},
            {"severity": "Medium", "issue": "unknown movement_id"},
            {"severity": "Medium", "issue": "duplicate date"},
            {"severity": "High", "issue": "invalid structured set"},
        ]
        write_json(tracker, {"fixture_issues": issues})
        changed = checker.summary()
        assert changed["status"] == "NEEDS_REVIEW"
        assert changed["issue_count"] == len(issues)
        assert changed["highest_severity"] == "HIGH"
        assert changed["data_fingerprint"] != healthy["data_fingerprint"]

        write_json(state_file, {"acknowledged": {issue_key(issues[0]): "2026-07-15T00:00:00"}})
        acknowledged = checker.summary()
        assert acknowledged["status"] == "NEEDS_REVIEW"
        assert acknowledged["issue_count"] == len(issues) - 1
        assert acknowledged["cached"] is False
        state_file.unlink()
        restored = checker.summary()
        assert restored["issue_count"] == len(issues) and restored["cached"] is False

        large = {"fixture_issues": issues, "records": [{"date": f"2026-01-{(index % 28) + 1:02d}"} for index in range(20_000)]}
        write_json(tracker, large)
        started = time.perf_counter()
        first_large = checker.summary()
        first_elapsed = time.perf_counter() - started
        started = time.perf_counter()
        second_large = checker.summary()
        cached_elapsed = time.perf_counter() - started
        assert first_large["cached"] is False and second_large["cached"] is True
        assert cached_elapsed < first_elapsed

        tracker.unlink()
        LOGGER.disabled = True
        try:
            unavailable = checker.summary()
        finally:
            LOGGER.disabled = False
        assert unavailable["status"] == "UNAVAILABLE"
        assert unavailable["issue_count"] is None
        assert unavailable["data_fingerprint"] is None

        app_js = (PROJECT_DIR / "web_desktop" / "frontend" / "app.js").read_text(encoding="utf-8")
        index_html = (PROJECT_DIR / "web_desktop" / "frontend" / "index.html").read_text(encoding="utf-8")
        styles_css = (PROJECT_DIR / "web_desktop" / "frontend" / "styles.css").read_text(encoding="utf-8")
        assert "Archive needs review" in app_js
        assert "Health check unavailable" in app_js
        assert "All healthy" not in app_js and "Data verified" not in app_js
        assert "health-nav-status" in index_html
        assert "localStorage" not in app_js
        assert 'data-issue-ack="${index}"' in app_js
        assert "await checksPage();await loadArchiveHealth()" in app_js
        assert '.nav-item[data-view="checks"]{position:relative;padding-right:44px}' in styles_css
        assert "grid-template-columns:repeat(2,minmax(0,1fr))" in styles_css
        assert "width:104px;white-space:nowrap" in styles_css

        write_json(
            tracker,
            {"daily_records": [{"id": "body-1", "Date": "2099-01-01", "Weight (kg)": None}],
             "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []},
        )
        write_json(dictionary, {"version": "1", "movements": []})
        real_service = LedgerWebService(tracker, dictionary, root / "backups")
        real_server = create_server(port=0, service=real_service)
        real_thread = threading.Thread(target=real_server.serve_forever, daemon=True)
        real_thread.start()
        try:
            real_base = f"http://127.0.0.1:{real_server.server_port}"
            with urllib.request.urlopen(real_base + "/api/data-check", timeout=3) as response:
                before_ack = json.loads(response.read().decode("utf-8"))
            assert len(before_ack["issues"]) == 1
            post_json(real_base + "/api/data-check/acknowledge", {"issue_key": before_ack["issues"][0]["issue_key"]})
            with urllib.request.urlopen(real_base + "/api/data-check", timeout=3) as response:
                after_ack = json.loads(response.read().decode("utf-8"))
            with urllib.request.urlopen(real_base + "/api/archive-health", timeout=3) as response:
                health_after_ack = json.loads(response.read().decode("utf-8"))
            assert len(after_ack["issues"]) == 0 and after_ack["acknowledged_count"] == 1
            assert health_after_ack["status"] == "OK" and health_after_ack["issue_count"] == 0
        finally:
            real_server.shutdown()
            real_server.server_close()
            real_thread.join(timeout=3)

        class HealthOnlyService:
            @staticmethod
            def archive_health() -> dict:
                return changed

        server = create_server(port=0, service=HealthOnlyService())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/api/archive-health", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert payload["status"] == "NEEDS_REVIEW"
            assert "issues" not in payload and "fixture_issues" not in payload
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

        healthy_dom = browser_dom(healthy)
        if healthy_dom is not None:
            assert 'class="health-nav-status" hidden=""' in healthy_dom
            assert 'aria-label="Data Check"' in healthy_dom
            review_dom = browser_dom(changed)
            assert 'health-nav-status needs-review' in review_dom
            assert f'>{len(issues)}</i>' in review_dom
            assert "Archive needs review" in review_dom
            two_digit_dom = browser_dom({**changed, "issue_count": 12})
            assert 'health-nav-status needs-review' in two_digit_dom
            assert '>12</i>' in two_digit_dom
            unavailable_dom = browser_dom(unavailable)
            assert 'health-nav-status unavailable' in unavailable_dom
            assert "Health check unavailable" in unavailable_dom

    print(
        "FITNESS_LEDGER_SILENT_HEALTH_OK "
        f"first_large_ms={first_elapsed * 1000:.3f} cached_large_ms={cached_elapsed * 1000:.3f}"
    )


if __name__ == "__main__":
    main()
