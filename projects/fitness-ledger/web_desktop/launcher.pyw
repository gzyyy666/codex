from __future__ import annotations

import os
import subprocess
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from backend.server import create_server
from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore


BASE_DIR = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8766"


def configure_data_module_registry() -> Path:
    registry = BASE_DIR.parent / "data" / "data_module_definitions.json"
    DataModuleDefinitionStore.initialize_empty(
        registry,
        backup_dir=BASE_DIR.parent / "data" / "backups" / "data_module_definitions",
    )
    os.environ.setdefault("FITNESS_LEDGER_DATA_MODULE_REGISTRY", str(registry))
    return registry


def find_edge() -> Path | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def wait_until_ready() -> None:
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=0.3) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("The local Fitness Ledger web service did not start.")


def main() -> None:
    configure_data_module_registry()
    server = create_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    wait_until_ready()
    edge = find_edge()
    if edge:
        profile = BASE_DIR / ".edge-profile"
        subprocess.Popen(
            [
                str(edge),
                f"--app={URL}",
                f"--user-data-dir={profile}",
                "--start-maximized",
                "--no-first-run",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # Edge may hand the app URL to an already-running browser process and
        # return immediately.  Its return is not a reliable signal that the
        # desktop app was closed, so keep owning the local service here.
        while True:
            time.sleep(60)
    else:
        webbrowser.open(URL)
        while True:
            time.sleep(60)
    server.shutdown()
    server.server_close()


if __name__ == "__main__":
    main()
