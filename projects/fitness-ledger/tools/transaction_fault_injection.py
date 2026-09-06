"""Candidate-local fault injection for the existing paired JSON writer."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ledger_commands as lc


OLD_TRACKER = {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []}
OLD_DICTIONARY = {"version": "1.0", "movements": []}
NEW_TRACKER = {**OLD_TRACKER, "audit_marker": "new-tracker"}
NEW_DICTIONARY = {**OLD_DICTIONARY, "audit_marker": "new-dictionary"}


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(root: Path) -> tuple[lc.LedgerCommandService, Path, Path]:
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    write_json(tracker, OLD_TRACKER)
    write_json(dictionary, OLD_DICTIONARY)
    backups.mkdir()
    tracker_backup = backups / "tracker.json"
    dictionary_backup = backups / "dictionary.json"
    shutil.copy2(tracker, tracker_backup)
    shutil.copy2(dictionary, dictionary_backup)
    service = lc.LedgerCommandService(tracker, dictionary, backups, lambda *_: {})
    return service, tracker_backup, dictionary_backup


def snapshots(service: lc.LedgerCommandService) -> dict:
    return {
        "tracker": json.loads(service.data_file.read_text(encoding="utf-8")),
        "dictionary": json.loads(service.dictionary_file.read_text(encoding="utf-8")),
    }


def worker(root: Path, crash_after: int) -> None:
    service, tracker_backup, dictionary_backup = prepare(root)
    original = lc._write_json_atomic
    calls = 0

    def crash_writer(path: Path, value: dict) -> None:
        nonlocal calls
        calls += 1
        original(path, value)
        if calls == crash_after:
            os._exit(90 + crash_after)

    with patch.object(lc, "_write_json_atomic", crash_writer):
        service._write_pair(NEW_TRACKER, NEW_DICTIONARY, tracker_backup, dictionary_backup)


def run_crash_case(crash_after: int) -> dict:
    with TemporaryDirectory(prefix=f"fl-transaction-crash-{crash_after}-") as temporary:
        root = Path(temporary)
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(root), str(crash_after)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        )
        tracker = json.loads((root / "tracker.json").read_text(encoding="utf-8"))
        dictionary = json.loads((root / "movement_dictionary.json").read_text(encoding="utf-8"))
        return {
            "case": f"process_exit_after_replace_{crash_after}",
            "exit_code": completed.returncode,
            "tracker_marker": tracker.get("audit_marker", ""),
            "dictionary_marker": dictionary.get("audit_marker", ""),
            "checkpoint_files": sorted(p.name for p in (root / "backups").glob("*.json")),
        }


def run_second_write_failure() -> dict:
    with TemporaryDirectory(prefix="fl-transaction-failure-") as temporary:
        root = Path(temporary)
        service, tracker_backup, dictionary_backup = prepare(root)
        original = lc._write_json_atomic
        calls = 0

        def fail_second(path: Path, value: dict) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected second-file replace failure")
            original(path, value)

        with patch.object(lc, "_write_json_atomic", fail_second):
            try:
                service._write_pair(NEW_TRACKER, NEW_DICTIONARY, tracker_backup, dictionary_backup)
            except lc.LedgerCommandError as error:
                failure = {"code": error.code, **error.details}
            else:
                raise AssertionError("injected write failure did not raise")
        state = snapshots(service)
        return {"case": "second_file_failure", "failure": failure, "state": state}


def run_rollback_failure() -> dict:
    with TemporaryDirectory(prefix="fl-transaction-rollback-") as temporary:
        root = Path(temporary)
        service, tracker_backup, dictionary_backup = prepare(root)
        original = lc._write_json_atomic
        calls = 0

        def fail_second(path: Path, value: dict) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                original(path, value)
                raise OSError("injected failure after second-file replace")
            original(path, value)

        original_copy = lc.shutil.copy2
        restore_calls = 0

        def fail_second_restore(source: Path, destination: Path, *args, **kwargs) -> None:
            nonlocal restore_calls
            restore_calls += 1
            if restore_calls == 2:
                raise OSError("injected rollback failure")
            original_copy(source, destination, *args, **kwargs)

        with patch.object(lc, "_write_json_atomic", fail_second), patch.object(lc.shutil, "copy2", fail_second_restore):
            try:
                service._write_pair(NEW_TRACKER, NEW_DICTIONARY, tracker_backup, dictionary_backup)
            except lc.LedgerCommandError as error:
                failure = {"code": error.code, **error.details}
            else:
                raise AssertionError("injected rollback failure did not raise")
        return {"case": "rollback_failure", "failure": failure, "state": snapshots(service)}


def main() -> None:
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), int(sys.argv[3]))
        return
    results = [run_crash_case(1), run_crash_case(2), run_second_write_failure(), run_rollback_failure()]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
