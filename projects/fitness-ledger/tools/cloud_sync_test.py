from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cloud_sync.sync_to_cloud import sync_payload, validate_payload


ENV_KEYS = [
    "FITNESS_LEDGER_CLOUD_SYNC_PROVIDER",
    "FITNESS_LEDGER_CLOUD_ENV_ID",
    "FITNESS_LEDGER_CLOUD_IMPORT_COMMAND",
    "FITNESS_LEDGER_CLOUD_META_COMMAND",
    "FITNESS_LEDGER_CLOUD_AUTO_SYNC",
]


def main() -> None:
    original_env = {key: os.environ.get(key) for key in ENV_KEYS}
    try:
        subprocess.run(
            [sys.executable, str(PROJECT / "cloud_sync" / "build_cloud_payload.py")],
            check=True,
        )

        dry_run = validate_payload()
        assert dry_run["status"] == "DRY_RUN"
        assert dry_run["network_request_made"] is False
        assert dry_run["payload_hash"]
        assert dry_run["sync_version"]

        for key in ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["FITNESS_LEDGER_CLOUD_SYNC_PROVIDER"] = "disabled"
        not_configured = sync_payload(force=True)
        assert not_configured["status"] == "NOT_CONFIGURED"
        assert not_configured["network_request_made"] is False

        os.environ["FITNESS_LEDGER_CLOUD_SYNC_PROVIDER"] = "command"
        os.environ["FITNESS_LEDGER_CLOUD_ENV_ID"] = "cloud-test"
        os.environ["FITNESS_LEDGER_CLOUD_IMPORT_COMMAND"] = "echo should-not-run"
        os.environ.pop("FITNESS_LEDGER_CLOUD_META_COMMAND", None)
        incomplete_command = sync_payload(force=True)
        assert incomplete_command["status"] == "NOT_CONFIGURED"
        assert incomplete_command["network_request_made"] is False
        assert "meta_command" in incomplete_command.get("config_status", {}).get("missing", [])

        os.environ["FITNESS_LEDGER_CLOUD_SYNC_PROVIDER"] = "mock"
        synced = sync_payload(force=True)
        assert synced["status"] == "SYNCED"
        assert synced["network_request_made"] is True
        assert synced["cloud_verification"]["verified"] is True
        assert synced["payload_hash"]

        unchanged = sync_payload(force=False)
        assert unchanged["status"] == "NO_CHANGES"
        assert unchanged["network_request_made"] is False
        assert unchanged["payload_hash"] == synced["payload_hash"]

        print("FITNESS_LEDGER_CLOUD_SYNC_OK")
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    main()
