from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "web_desktop"))

from launcher_instance import SingleInstanceMutex, wait_for_window_close
import launcher
from launcher import run_server_until_window_closes
from backend.server import create_server


class FakeServer:
    def __init__(self) -> None:
        self.shutdown_called = False
        self.close_called = False

    def serve_forever(self) -> None:
        while not self.shutdown_called:
            time.sleep(0.001)

    def shutdown(self) -> None:
        self.shutdown_called = True

    def server_close(self) -> None:
        self.close_called = True


class WebLauncherLifecycleTests(unittest.TestCase):
    def test_secondary_launcher_reuses_service_without_creating_server(self) -> None:
        mutex = Mock()
        mutex.acquire.return_value = False
        with (
            patch("launcher.SingleInstanceMutex", return_value=mutex),
            patch("launcher.wait_until_ready") as wait_ready,
            patch("launcher.open_desktop") as open_desktop,
            patch("launcher.configure_data_module_registry") as configure,
            patch("launcher.create_server") as create_server,
        ):
            launcher.main()

        wait_ready.assert_called_once()
        open_desktop.assert_called_once()
        configure.assert_not_called()
        create_server.assert_not_called()
        mutex.close.assert_called_once()

    def test_old_service_port_conflict_shows_one_time_migration_guidance(self) -> None:
        mutex = Mock()
        mutex.acquire.return_value = True
        messages = []
        with (
            patch("launcher.SingleInstanceMutex", return_value=mutex),
            patch("launcher.configure_data_module_registry"),
            patch("launcher.create_server", side_effect=OSError("address already in use")),
            patch("launcher.wait_until_ready"),
            patch("launcher.show_startup_error", side_effect=messages.append),
        ):
            launcher.main()

        self.assertEqual(len(messages), 1)
        self.assertIn("Restart Windows once", messages[0])
        mutex.close.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Windows named mutex behavior")
    def test_secondary_launcher_does_not_acquire_existing_mutex(self) -> None:
        name = f"Local\\FitnessLedger.WebDesktop.Test.{os.getpid()}"
        owner = SingleInstanceMutex(name)
        secondary = SingleInstanceMutex(name)
        try:
            self.assertTrue(owner.acquire())
            self.assertFalse(secondary.acquire())
        finally:
            secondary.close()
            owner.close()

    @unittest.skipUnless(os.name == "nt", "Windows named mutex behavior")
    def test_second_process_cannot_acquire_live_instance_mutex(self) -> None:
        name = f"Local\\FitnessLedger.WebDesktop.ChildTest.{os.getpid()}"
        owner = SingleInstanceMutex(name)
        self.assertTrue(owner.acquire())
        child_code = (
            "import sys; "
            f"sys.path.insert(0, {str(PROJECT_ROOT / 'web_desktop')!r}); "
            "from launcher_instance import SingleInstanceMutex; "
            f"mutex=SingleInstanceMutex({name!r}); "
            "print('PRIMARY' if mutex.acquire() else 'SECONDARY', flush=True); "
            "mutex.close()"
        )
        try:
            result = subprocess.run(
                [sys.executable, "-c", child_code],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), "SECONDARY")
        finally:
            owner.close()

    def test_second_http_server_cannot_reuse_live_service_port(self) -> None:
        first = create_server("127.0.0.1", 0, service=object())
        port = first.server_address[1]
        try:
            with self.assertRaises(OSError):
                create_server("127.0.0.1", port, service=object())
        finally:
            first.server_close()
        replacement = create_server("127.0.0.1", port, service=object())
        replacement.server_close()

    def test_server_is_closed_after_window_closes(self) -> None:
        server = FakeServer()
        opened = []

        result = run_server_until_window_closes(
            server,
            open_window=lambda: opened.append(True),
            wait=lambda: True,
            wait_ready=lambda: None,
        )

        self.assertTrue(result)
        self.assertEqual(opened, [True])
        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.close_called)

    def test_server_is_closed_if_window_wait_fails(self) -> None:
        server = FakeServer()

        self.assertFalse(run_server_until_window_closes(server, wait=lambda: False, wait_ready=lambda: None))

        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.close_called)

    def test_server_is_closed_if_window_launch_fails(self) -> None:
        server = FakeServer()

        def fail_to_open() -> None:
            raise RuntimeError("browser start failed")

        with self.assertRaisesRegex(RuntimeError, "browser start failed"):
            run_server_until_window_closes(
                server,
                open_window=fail_to_open,
                wait_ready=lambda: None,
            )

        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.close_called)

    def test_window_wait_requires_appearance_then_disappearance(self) -> None:
        states = iter([False, True, True, False])

        with patch("launcher_instance.time.sleep"):
            self.assertTrue(
                wait_for_window_close(
                    startup_timeout=1,
                    poll_interval=0,
                    is_window_open=lambda _title: next(states),
                )
            )


if __name__ == "__main__":
    unittest.main()
