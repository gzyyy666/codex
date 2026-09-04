"""Durable local consumer for the CloudBase phone-share inbox."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


SCHEMA_VERSION = "phone-inbox-local-v1"
KEEP_COUNT = 7


class PhoneInboxError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _timestamp(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _message_id(item: dict[str, Any]) -> str:
    value = item.get("_id") or item.get("message_id")
    if not str(value or "").strip():
        raise PhoneInboxError("PHONE_INBOX_MESSAGE_ID_REQUIRED", "Cloud inbox item has no stable message ID.")
    return str(value).strip()


def _normalize(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise PhoneInboxError("PHONE_INBOX_ITEM_INVALID", "Cloud inbox items must be JSON objects.")
    nested = item.get("data") if isinstance(item.get("data"), dict) else {}
    normalized = {**nested, **item}
    return {
        "_id": _message_id(normalized),
        "owner_uid": str(normalized.get("owner_uid") or ""),
        "client_id": str(normalized.get("client_id") or ""),
        "title": str(normalized.get("title") or ""),
        "text": str(normalized.get("text") or ""),
        "source": str(normalized.get("source") or ""),
        "status": str(normalized.get("status") or "pending"),
        "received_at": normalized.get("received_at", 0),
        "updated_at": normalized.get("updated_at", 0),
        "expires_at": normalized.get("expires_at", 0),
    }


def _sort_key(item: dict[str, Any]) -> tuple[float, str]:
    # Product order is latest first; the ID makes equal timestamps deterministic.
    return (_timestamp(item.get("received_at")), str(item.get("_id") or ""))


def retain_latest(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in items:
        item = _normalize(raw)
        if item.get("status") == "expired":
            continue
        by_id[item["_id"]] = item
    return sorted(by_id.values(), key=_sort_key, reverse=True)[:KEEP_COUNT]


class PhoneInboxStore:
    """A locked, atomic JSON store for the desktop's local inbox."""

    def __init__(self, path: Path, replace: Callable[[str, str], None] | None = None) -> None:
        self.path = Path(path)
        self._replace = replace or os.replace
        self._lock = threading.RLock()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "items": [],
            "sync": {"last_received_at": 0, "last_message_id": "", "last_success_at": ""},
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PhoneInboxError("PHONE_INBOX_LOCAL_CORRUPT", f"Local phone inbox is unreadable: {self.path} ({exc})") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("items"), list):
            raise PhoneInboxError("PHONE_INBOX_LOCAL_CORRUPT", f"Local phone inbox has an invalid schema: {self.path}")
        try:
            payload["items"] = retain_latest(payload["items"])
        except PhoneInboxError as exc:
            raise PhoneInboxError("PHONE_INBOX_LOCAL_CORRUPT", f"Local phone inbox contains invalid data: {exc}") from exc
        if not isinstance(payload.get("sync"), dict):
            raise PhoneInboxError("PHONE_INBOX_LOCAL_CORRUPT", f"Local phone inbox has an invalid sync state: {self.path}")
        return payload

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = self._read()
            return {"status": "ready", "schema_version": SCHEMA_VERSION, "path": str(self.path), "items": payload["items"], "sync": payload["sync"]}

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as handle:
                temporary = handle.name
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._replace(temporary, str(self.path))
            temporary = None
        finally:
            if temporary:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    def sync(self, cloud_items: Iterable[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            current = self._read()
            incoming = [_normalize(item) for item in cloud_items]
            merged = retain_latest([*current["items"], *incoming])
            newest = max(incoming, key=_sort_key, default=None)
            sync = dict(current["sync"])
            if newest is not None:
                sync.update({"last_received_at": newest.get("received_at", 0), "last_message_id": newest["_id"]})
            sync["last_success_at"] = _now()
            payload = {"schema_version": SCHEMA_VERSION, "items": merged, "sync": sync}
            self._atomic_write(payload)
            return {"status": "ready", "schema_version": SCHEMA_VERSION, "path": str(self.path), "items": merged, "sync": sync, "received_count": len(incoming), "newest_message_id": newest["_id"] if newest else ""}
