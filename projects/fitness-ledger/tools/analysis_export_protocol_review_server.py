"""Anonymous browser Review server for Analysis Export Protocol v1.1."""
from __future__ import annotations

import sys
import json
import tempfile
import threading
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from tools.archive_navigation_test import fixture  # noqa: E402
from web_desktop.backend.analysis_export_protocol import AnonymousFixtureProvider, AnalysisExportProtocolService  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def main() -> None:
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-analysis-export-review-")
    root = Path(temp.name)
    tracker_data, dictionary_data = fixture()
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    tracker.write_text(json.dumps(tracker_data, ensure_ascii=False), encoding="utf-8")
    dictionary.write_text(json.dumps(dictionary_data, ensure_ascii=False), encoding="utf-8")
    service = LedgerWebService(
        tracker,
        dictionary,
        root / "backups",
        analysis_export_protocol=AnalysisExportProtocolService(AnonymousFixtureProvider()),
    )
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Fitness Ledger Analysis Export Protocol review: http://127.0.0.1:{server.server_port}/#tools?panel=export", flush=True)
    print("Anonymous fixture only; no formal data, model, executor, Cloud, or writes.", flush=True)
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
