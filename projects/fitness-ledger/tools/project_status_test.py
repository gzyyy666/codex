from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-project-state-") as temp:
        env = {**os.environ, "FITNESS_LEDGER_STATE_DIR": temp}
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT / "tools" / "project_status.py"),
                "--write",
                "--handoff",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        state = json.loads(completed.stdout)
        assert state["schema"] == 1
        assert len(state["git"]["head"]) == 40
        assert len(state["git"]["main"]) == 40
        assert "sha256" in state["formal"]["tracker"]
        assert "sha256" in state["formal"]["movement_dictionary"]
        assert "daily_records" not in completed.stdout
        assert state["cloud_sync"]["status"]
        assert isinstance(state["service"]["available"], bool)
        assert Path(state["outputs"]["state_file"]).is_file()
        handoff_path = Path(state["outputs"]["handoff_file"])
        assert handoff_path.is_file()
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert handoff["closure_state"] in {
            "sealed_on_main",
            "main_requires_formal_deployment",
            "review_ready",
            "worktree_dirty",
            "main_state",
            "development",
        }
        assert handoff["integration_reason"]
        assert set(handoff["main_sync"]) == {"ahead", "behind"}
        assert "sha256" in handoff["formal_data"]["tracker"]
        assert "sha256" in handoff["formal_data"]["movement_dictionary"]
        assert isinstance(handoff["service"]["available"], bool)
    print("FITNESS_LEDGER_PROJECT_STATUS_OK")


if __name__ == "__main__":
    main()
