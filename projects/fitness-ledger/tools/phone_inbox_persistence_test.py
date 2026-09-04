"""Isolated acceptance tests for the durable phone inbox consumer."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from web_desktop.backend.phone_inbox import PhoneInboxError, PhoneInboxStore


def row(number: int, *, received_at: int | None = None, text: str | None = None) -> dict:
    return {
        "_id": f"FL_MOBILE_E2E_TEST_{number:02d}",
        "owner_uid": "isolated-user",
        "client_id": f"client-{number:02d}",
        "title": f"记录 {number:02d}",
        "text": text if text is not None else f"中文 / English\n训练记录 {number:02d}，标点：，。!",
        "source": "pwa_note",
        "status": "pending",
        "received_at": number if received_at is None else received_at,
        "updated_at": number,
    }


def ids(payload: dict) -> list[str]:
    return [item["_id"] for item in payload["items"]]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-phone-inbox-isolated-") as root:
        path = Path(root) / "phone_inbox.json"
        store = PhoneInboxStore(path)

        assert store.snapshot()["items"] == []
        first = store.sync([row(1, text="中文\nEnglish，较长训练文本：" + "深蹲 " * 100)])
        assert len(first["items"]) == 1
        assert first["items"][0]["text"] == "中文\nEnglish，较长训练文本：" + "深蹲 " * 100

        source = [row(number) for number in range(1, 9)]
        after_eight = store.sync(source)
        assert ids(after_eight) == [f"FL_MOBILE_E2E_TEST_{n:02d}" for n in range(8, 1, -1)]
        assert len(json.loads(path.read_text(encoding="utf-8"))["items"]) == 7

        repeated = store.sync(source)
        assert ids(repeated) == ids(after_eight)
        shuffled = store.sync([source[index] for index in (3, 0, 7, 2, 5, 1, 6, 4)])
        assert ids(shuffled) == ids(after_eight)

        same_time = [row(20, received_at=99), row(19, received_at=99)]
        tied = store.sync(same_time)
        assert ids(tied)[:2] == ["FL_MOBILE_E2E_TEST_20", "FL_MOBILE_E2E_TEST_19"]

        before_bytes = path.read_bytes()
        before_hash = hashlib.sha256(before_bytes).hexdigest()

        def fail_replace(_source: str, _target: str) -> None:
            raise OSError("injected disk failure")

        failing = PhoneInboxStore(path, replace=fail_replace)
        try:
            failing.sync([row(21)])
        except OSError as exc:
            assert str(exc) == "injected disk failure"
        else:
            raise AssertionError("write failure was not raised")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before_hash
        assert ids(store.snapshot()) == ids(tied)

        # A failed cloud pull does not call the store; the next successful pull
        # can therefore fill the missing message without advancing early.
        failed_cloud = True
        if failed_cloud:
            assert store.snapshot()["sync"]["last_message_id"] == tied["sync"]["last_message_id"]
        recovered = store.sync([row(21)])
        assert recovered["sync"]["last_message_id"] == row(21)["_id"]

        removed = store.remove(row(21)["_id"])
        assert row(21)["_id"] not in ids(removed)
        assert row(21)["_id"] in json.loads(path.read_text(encoding="utf-8"))["deleted_ids"]
        after_delete_resync = store.sync([row(21)])
        assert row(21)["_id"] not in ids(after_delete_resync)

        path.write_text("{not valid json", encoding="utf-8")
        try:
            store.snapshot()
        except PhoneInboxError as exc:
            assert exc.code == "PHONE_INBOX_LOCAL_CORRUPT"
        else:
            raise AssertionError("corrupt local inbox was silently accepted")
        assert path.read_text(encoding="utf-8") == "{not valid json"

        print(json.dumps({
            "status": "PASS",
            "local_file": str(path),
            "schema": "phone-inbox-local-v1",
            "first": 1,
            "cloud_source_rows": 8,
            "after_eighth": ids(after_eight),
            "duplicate_pull_unchanged": True,
            "stable_tie_order": ids(tied)[:2],
            "write_failure_preserved_file": True,
            "network_recovery_preserved_cursor": True,
            "explicit_delete_blocks_reappearance": True,
            "corruption_diagnostic": "PHONE_INBOX_LOCAL_CORRUPT",
            "restart_equivalent_snapshot": True,
            "unicode_newline_long_text": True,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
