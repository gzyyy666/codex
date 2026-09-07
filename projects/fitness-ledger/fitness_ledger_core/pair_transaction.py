"""Crash-recovery journal for the two protected Fitness Ledger JSON files.

The journal is deliberately small and local.  It records the existing paired
checkpoints before either protected file is replaced.  A process that exits
after one replacement therefore leaves enough information for the next read
or write to restore the last complete pair.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

JOURNAL_VERSION = "fitness-ledger-pair-transaction-v1"


class PairTransactionError(RuntimeError):
    """Raised when a pending pair cannot be recovered safely."""


def journal_path(data_file: Path) -> Path:
    return Path(data_file).parent / ".fitness-ledger-pair-transaction.json"


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        payload = json.dumps(value, ensure_ascii=False, indent=2)
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def begin(journal: Path, data_file: Path, dictionary_file: Path, tracker_backup: Path, dictionary_backup: Path) -> None:
    _write_json_atomic(
        journal,
        {
            "format": JOURNAL_VERSION,
            "status": "prepared",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "data_file": str(Path(data_file).resolve()),
            "dictionary_file": str(Path(dictionary_file).resolve()),
            "tracker_backup": str(Path(tracker_backup).resolve()),
            "dictionary_backup": str(Path(dictionary_backup).resolve()),
        },
    )


def commit(journal: Path) -> None:
    payload = json.loads(Path(journal).read_text(encoding="utf-8"))
    payload["status"] = "committed"
    payload["committed_at"] = datetime.now(timezone.utc).isoformat()
    _write_json_atomic(Path(journal), payload)


def _validate_file(path: Path) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact parser exception varies
        raise PairTransactionError(f"paired file is not valid JSON: {path}") from exc


def recover(journal: Path, data_file: Path, dictionary_file: Path) -> dict:
    """Recover a pending transaction and return an auditable result.

    A prepared transaction is always rolled back to both checkpoints.  A
    committed transaction is retained after validating both files; only its
    journal is cleaned.  Unknown or incomplete journals fail closed and remain
    on disk for manual review.
    """

    journal = Path(journal)
    if not journal.exists():
        return {"status": "none", "journal": str(journal)}
    try:
        payload = json.loads(journal.read_text(encoding="utf-8"))
        if payload.get("format") != JOURNAL_VERSION:
            raise PairTransactionError("unsupported pair transaction journal format")
        if Path(payload.get("data_file", "")).resolve() != Path(data_file).resolve():
            raise PairTransactionError("pair transaction data path does not match")
        if Path(payload.get("dictionary_file", "")).resolve() != Path(dictionary_file).resolve():
            raise PairTransactionError("pair transaction dictionary path does not match")
        status = payload.get("status")
        if status == "committed":
            _validate_file(Path(data_file))
            _validate_file(Path(dictionary_file))
            journal.unlink(missing_ok=True)
            return {"status": "committed_kept", "journal": str(journal)}
        if status != "prepared":
            raise PairTransactionError("unknown pair transaction status")
        tracker_backup = Path(payload["tracker_backup"])
        dictionary_backup = Path(payload["dictionary_backup"])
        if not tracker_backup.is_file() or not dictionary_backup.is_file():
            raise PairTransactionError("paired transaction checkpoint is missing")
        shutil.copy2(tracker_backup, data_file)
        shutil.copy2(dictionary_backup, dictionary_file)
        _validate_file(Path(data_file))
        _validate_file(Path(dictionary_file))
        journal.unlink(missing_ok=True)
        return {"status": "rolled_back", "journal": str(journal)}
    except PairTransactionError:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise PairTransactionError("paired transaction recovery failed") from exc
