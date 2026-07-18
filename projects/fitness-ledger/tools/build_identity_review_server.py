"""Anonymous local review servers for the runtime identity marker.

Four ports expose the same UI with safe fixture data and explicit identity
states. This harness never reads the formal data directory or Cloud Sync.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
import sys
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from web_desktop.backend.server import LedgerWebService, create_server


def fixture_service(root: Path, identity: dict) -> LedgerWebService:
    tracker = root / f"tracker-{identity['status']}.json"
    dictionary = root / f"dictionary-{identity['status']}.json"
    tracker.write_text(json.dumps({"daily_records": [], "diet_records": [], "training_sessions": [], "raw_entries": [], "movements": {}}, ensure_ascii=False), encoding="utf-8")
    dictionary.write_text(json.dumps({"movements": []}, ensure_ascii=False), encoding="utf-8")
    return LedgerWebService(tracker, dictionary, root / "backups", build_info_override=identity)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-port", type=int, default=8794)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix="fitness-ledger-build-review-"))
    fake_sha = "e" * 40
    identities = [
        ("formal", {"mode": "formal", "status": "PUBLISHED", "source": "deployment_manifest", "commit_sha": fake_sha, "short_sha": fake_sha[:7], "branch": "main", "main_sha": fake_sha, "origin_main_sha": fake_sha, "push_verified": True, "generated_at": "2026-07-18T00:00:00Z", "dirty": False, "tag": "review-formal"}),
        ("preview-clean", {"mode": "preview", "status": "PREVIEW", "source": "worktree", "commit_sha": "f" * 40, "short_sha": "fffffff", "branch": "feat/review", "main_sha": fake_sha, "origin_main_sha": fake_sha, "push_verified": False, "generated_at": "", "dirty": False, "tag": ""}),
        ("preview-dirty", {"mode": "preview", "status": "PREVIEW", "source": "worktree", "commit_sha": "1" * 40, "short_sha": "1111111", "branch": "feat/review", "main_sha": fake_sha, "origin_main_sha": fake_sha, "push_verified": False, "generated_at": "", "dirty": True, "tag": ""}),
        ("unknown", {"mode": "unknown", "status": "UNKNOWN", "source": "unknown", "commit_sha": "", "short_sha": "", "branch": "", "main_sha": "", "origin_main_sha": "", "push_verified": None, "generated_at": "", "dirty": None, "tag": ""}),
    ]
    servers = []
    for offset, (label, identity) in enumerate(identities):
        server = create_server(port=args.base_port + offset, service=fixture_service(root, identity))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        print(f"{label}: http://127.0.0.1:{server.server_port}/#home", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        for server in servers:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
