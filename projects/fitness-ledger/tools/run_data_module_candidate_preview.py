"""Start the isolated Data Module human-review preview.

This launcher creates an anonymous temporary tracker and movement dictionary,
uses the candidate registry from this worktree, and binds only to localhost.
It never reads the formal Fitness Ledger directory unless the caller edits the
script, which is intentionally outside the supported review path.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_anonymous_fixture(root: Path) -> tuple[Path, Path, Path]:
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    _write_json(
        tracker,
        {
            "daily_records": [{"Date": "2026-08-12", "Weight (kg)": 70}],
            "diet_records": [],
            "training_sessions": [],
            "movements": {},
            "raw_entries": [],
            "data_module_records": [],
        },
    )
    _write_json(dictionary, {"version": "1.0", "movements": []})
    return tracker, dictionary, backups


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the isolated Data Module candidate preview.")
    parser.add_argument("--port", type=int, default=8767, help="localhost port (default: 8767)")
    parser.add_argument("--open", action="store_true", help="open the review page in the default browser")
    args = parser.parse_args()

    registry = PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"
    if not registry.is_file():
        raise SystemExit(f"Candidate registry not found: {registry}")

    with tempfile.TemporaryDirectory(prefix="fitness-ledger-data-module-review-") as runtime:
        tracker, dictionary, backups = _build_anonymous_fixture(Path(runtime))
        definition_store = Path(runtime) / "data_module_definitions.json"
        DataModuleDefinitionStore.initialize(definition_store, registry)
        service = LedgerWebService(
            tracker,
            dictionary,
            backups,
            build_info_override={
                "branch": "codex/fitness-ledger-data-module-candidate-20260812",
                "review_fixture": "anonymous-temporary-fixture",
                "formal_data_used": False,
            },
            data_module_registry_file=definition_store,
        )
        server = create_server("127.0.0.1", args.port, service)
        url = f"http://127.0.0.1:{server.server_address[1]}/data-module-candidate.html"
        print("Data Module Candidate Preview")
        print(f"URL: {url}")
        print("Fixture: anonymous temporary tracker; deleted when the process exits")
        print("Stop: Ctrl+C")
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping candidate preview...")
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
