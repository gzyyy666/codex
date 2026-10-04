from __future__ import annotations

import os
import subprocess
import time
import urllib.request
import webbrowser
from pathlib import Path

from backend.server import create_server
from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore
from launcher_instance import SingleInstanceMutex, show_startup_error, wait_for_window_close


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


def open_desktop() -> None:
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
    else:
        webbrowser.open(URL)


def wait_until_ready() -> None:
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{URL}/api/health", timeout=0.3) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("The local Fitness Ledger web service did not start.")


def run_server_until_window_closes(
    server,
    *,
    open_window=open_desktop,
    wait=wait_for_window_close,
    wait_ready=wait_until_ready,
) -> bool:
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        wait_ready()
        open_window()
        return wait()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def main() -> None:
    mutex = SingleInstanceMutex("Local\\FitnessLedger.WebDesktop")
    try:
        if not mutex.acquire():
            # Windows redirects this launch to the existing Edge app profile.
            # The secondary launcher exits without binding the service port.
            try:
                wait_until_ready()
            except RuntimeError as error:
                show_startup_error(str(error))
                return
            open_desktop()
            return
        configure_data_module_registry()
        try:
            server = create_server()
        except OSError as error:
            try:
                wait_until_ready()
            except RuntimeError:
                show_startup_error(f"The desktop service port is unavailable.\n\nDetails: {error}")
            else:
                show_startup_error(
                    "An older Fitness Ledger service is still running. Restart Windows once to clear the "
                    "pre-fix background launchers, then open Fitness Ledger again. Future launches will "
                    "be managed by the single-instance launcher.\n\n"
                    f"Details: {error}"
                )
            return
        window_closed = run_server_until_window_closes(server)
        if not window_closed:
            show_startup_error("Fitness Ledger did not open its desktop window. The local service has been stopped.")
    except Exception as error:
        show_startup_error(f"Fitness Ledger could not start.\n\nDetails: {error}")
    finally:
        mutex.close()


if __name__ == "__main__":
    main()
