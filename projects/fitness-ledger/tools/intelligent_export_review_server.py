"""Anonymous Intelligent Export Web Review server; never loads formal data."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from tools.intent_real_acceptance import fixture  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def git_value(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=PROJECT, check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-intelligent-export-review-")
    root = Path(temp.name)
    tracker, dictionary = fixture(root)
    commit = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    service = LedgerWebService(
        tracker,
        dictionary,
        root / "backups",
        build_info_override={
            "mode": "preview",
            "status": "PREVIEW",
            "branch": branch,
            "commit_sha": commit,
            "main_sha": git_value("rev-parse", "main"),
            "origin_main_sha": git_value("rev-parse", "origin/main"),
            "dirty": False,
            "push_verified": False,
            "tag": "",
            "data_mode": "ANONYMOUS_REVIEW",
            "candidate": "Intelligent Export deterministic Core + Web",
        },
    )
    server = create_server(host="127.0.0.1", port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Fitness Ledger Intelligent Export Web Review: http://127.0.0.1:{server.server_port}/#tools?panel=export", flush=True)
    print("Data mode: anonymous temporary fixture; formal tracker/dictionary are not loaded.", flush=True)
    print("Review: Tools → Export → deterministic request preview; R1–R12 buttons are embedded in the page.", flush=True)
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        temp.cleanup()


if __name__ == "__main__":
    main()
