"""Isolated tests for local bind and legacy Cloud Sync safety boundaries."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloud_sync.upload_to_cloudbase import config_status, upload_payload
from mobile_viewer.app import main as mobile_viewer_main


def test_mobile_viewer_is_localhost_only() -> None:
    with patch("mobile_viewer.app.Flask.run") as run:
        mobile_viewer_main()
    assert run.call_args.kwargs["host"] == "127.0.0.1"
    assert run.call_args.kwargs["port"] == 5055


def test_legacy_command_provider_is_disabled() -> None:
    config = {
        "provider": "command",
        "environment_id": "audit-only",
        "import_command": "echo MUST_NOT_RUN",
        "meta_command": "echo MUST_NOT_RUN",
    }
    status = config_status(config)
    assert status["ready"] is False
    assert status["upload_enabled"] is False
    assert "legacy_command_provider_disabled" in status["missing"]


def test_disabled_command_provider_does_not_execute_or_write() -> None:
    # The config and marker path are isolated and deliberately have no
    # credential values.  A legacy command provider must be rejected before
    # the manifest or any configured command can be executed.
    with TemporaryDirectory(prefix="fl-command-disabled-") as temporary:
        root = Path(temporary)
        marker = root / "must-not-run.txt"
        config_path = root / "config.json"
        config_path.write_text(
            json.dumps(
                {
                    "provider": "command",
                    "environment_id": "audit-only",
                    "import_command": f"echo SHOULD_NOT_RUN > {marker}",
                    "meta_command": f"echo SHOULD_NOT_RUN > {marker}",
                }
            ),
            encoding="utf-8",
        )
        with patch("cloud_sync.upload_to_cloudbase.load_manifest", return_value={"sync_version": "audit"}):
            result = upload_payload(config_path)
        assert result["status"] == "NOT_CONFIGURED"
        assert "legacy_command_provider_disabled" in result["config_status"]["missing"]
        assert not marker.exists()


if __name__ == "__main__":
    test_mobile_viewer_is_localhost_only()
    test_legacy_command_provider_is_disabled()
    test_disabled_command_provider_does_not_execute_or_write()
    print("FITNESS_LEDGER_SECURITY_BOUNDARY_OK")
