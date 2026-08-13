"""Run the isolated Formal Web Integrated Review Mirror.

The mirror always receives explicit temporary data paths.  It never resolves
the formal Fitness Ledger directory and never starts a cloud or Mini process.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_sandbox(root: Path) -> tuple[Path, Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    registry = root / "data_module_definitions.json"
    if not tracker.exists():
        write_json(
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
    if not dictionary.exists():
        write_json(dictionary, {"version": "1.0", "movements": []})
    seed = PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"
    if not registry.exists():
        DataModuleDefinitionStore.initialize(registry, seed, backup_dir=root / "definition_backups")
    return tracker, dictionary, backups, registry


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the isolated Fitness Ledger Formal Web review mirror.")
    parser.add_argument("--port", type=int, default=8768, help="localhost port (default: 8768)")
    parser.add_argument("--open", action="store_true", help="open the mirror in the default browser")
    parser.add_argument("--sandbox", type=Path, help="optional persistent sandbox directory for restart review")
    args = parser.parse_args()

    temporary = args.sandbox is None
    runtime = args.sandbox.resolve() if args.sandbox else Path(tempfile.mkdtemp(prefix="fitness-ledger-formal-mirror-"))
    tracker, dictionary, backups, registry = ensure_sandbox(runtime)
    service = LedgerWebService(
        tracker,
        dictionary,
        backups,
        build_info_override={
            "mode": "FORMAL WEB REVIEW MIRROR",
            "status": "PREVIEW",
            "branch": "codex/fitness-ledger-formal-mirror-20260813",
            "review_fixture": "anonymous-temporary-fixture",
            "formal_data_used": False,
            "cloud_mutation": False,
            "mini_publish": False,
        },
        data_module_registry_file=registry,
    )
    server = create_server("127.0.0.1", args.port, service)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print("Fitness Ledger Formal Web Integrated Review Mirror")
    print(f"URL: {url}")
    print(f"Sandbox: {runtime}")
    print("Fixture: anonymous local data; no formal tracker or deployment data is used")
    print("Stop: Ctrl+C")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Formal Web review mirror...")
    finally:
        server.server_close()
        if temporary:
            shutil.rmtree(runtime, ignore_errors=True)


if __name__ == "__main__":
    main()
