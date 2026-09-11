"""Run an isolated PWA review for Complex Set + Session Superset."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from mobile_viewer.app import create_app  # noqa: E402
from mobile_viewer.data_access import LedgerDataAccess  # noqa: E402
from tools.complex_set_superset_browser_test import write_fixture  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5056)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-complex-superset-pwa-") as temp:
        root = Path(temp)
        write_fixture(root)
        app = create_app(LedgerDataAccess(root / "tracker.json", root / "movement_dictionary.json"))
        print(f"URL: http://127.0.0.1:{args.port}/pwa/#training", flush=True)
        print("Fixture: anonymous and temporary; no formal tracker or Cloud mutation", flush=True)
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
