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

from fitness_ledger_core.data_quality_view import LOGGER, SilentHealthCheck
from web_desktop.backend.server import create_server


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
        write_json(tracker, {"fixture_issues": []})
        write_json(dictionary, {"movements": []})
        checker = SilentHealthCheck(tracker, dictionary, FakeStable)

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
        assert "Archive needs review" in app_js
        assert "Health check unavailable" in app_js
        assert "All healthy" not in app_js and "Data verified" not in app_js
        assert "health-nav-status" in index_html
        assert "localStorage" not in app_js

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
            unavailable_dom = browser_dom(unavailable)
            assert 'health-nav-status unavailable' in unavailable_dom
            assert "Health check unavailable" in unavailable_dom

    print(
        "FITNESS_LEDGER_SILENT_HEALTH_OK "
        f"first_large_ms={first_elapsed * 1000:.3f} cached_large_ms={cached_elapsed * 1000:.3f}"
    )


if __name__ == "__main__":
    main()
