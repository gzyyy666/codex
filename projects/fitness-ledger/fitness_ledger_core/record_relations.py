"""Stable relationships shared by the command and read models.

The tracker is intentionally still JSON.  This module makes the existing JSON
shape explicit without making a second business store: legacy rows are
normalised in memory on read and are persisted atomically by the next command
write.  All generated identifiers are deterministic so the migration is
idempotent and safe to preview on a copy of the data.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from typing import Any


RELATION_SCHEMA_VERSION = "fitness-ledger-relations-v1"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def canonical_date(value: Any) -> str:
    return str(value or "")[:10]


def record_day_id(value: Any) -> str:
    day = canonical_date(value)
    return f"day:{day}" if day else ""


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _rows(database: dict, key: str) -> list[dict]:
    value = database.get(key, [])
    return value if isinstance(value, list) else []


def _movement_rows(database: dict) -> list[dict]:
    value = database.get("movements", {})
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _touch_entity(row: dict, fallback_created: str = "") -> bool:
    changed = False
    if not str(row.get("id", "")).strip():
        row["id"] = _stable_id("record", {key: value for key, value in row.items() if key not in {"updated_at", "revision"}})
        changed = True
    if not row.get("revision"):
        row["revision"] = 1
        changed = True
    if "updated_at" not in row:
        row["updated_at"] = str(row.get("created_at") or fallback_created or "")
        changed = True
    return changed


def migrate_state(database: dict, dictionary: dict) -> tuple[dict, dict, dict]:
    """Return a normalised copy and a small migration report.

    No file is touched here.  Callers that are writing the copy get the usual
    paired checkpoint/rollback behaviour from ``LedgerCommandService``.
    """
    db = copy.deepcopy(database if isinstance(database, dict) else {})
    lexicon = copy.deepcopy(dictionary if isinstance(dictionary, dict) else {})
    report = {"changed": False, "added_fields": 0, "record_days": 0, "raw_revisions": 0}
    db.setdefault("daily_records", [])
    db.setdefault("diet_records", [])
    db.setdefault("training_sessions", [])
    db.setdefault("raw_entries", [])
    db.setdefault("data_module_records", [])
    db.setdefault("movements", {})
    db.setdefault("record_days", [])
    db.setdefault("raw_entry_revisions", [])

    def mark(changed: bool) -> None:
        if changed:
            report["changed"] = True
            report["added_fields"] += 1

    dates: set[str] = set()
    for collection, date_field in (
        ("daily_records", "Date"),
        ("diet_records", "Date"),
        ("training_sessions", "Date"),
        ("data_module_records", "date"),
        ("raw_entries", "date"),
    ):
        for row in _rows(db, collection):
            dates.add(canonical_date(row.get(date_field)))
            mark(_touch_entity(row, canonical_date(row.get(date_field))))
    for movement in _movement_rows(db):
        mark(_touch_entity(movement, ""))
        for history in movement.setdefault("history", []) or []:
            dates.add(canonical_date(history.get("date")))
            mark(_touch_entity(history, canonical_date(history.get("date"))))

    days_by_id = {str(row.get("record_day_id")): row for row in _rows(db, "record_days") if row.get("record_day_id")}
    days_by_date = {canonical_date(row.get("date")): row for row in _rows(db, "record_days") if canonical_date(row.get("date"))}
    for day in sorted(item for item in dates if item):
        day_id = record_day_id(day)
        row = days_by_id.get(day_id) or days_by_date.get(day)
        if row is None:
            row = {"record_day_id": day_id, "date": day, "revision": 1, "created_at": f"{day}T00:00:00", "updated_at": f"{day}T00:00:00"}
            db["record_days"].append(row)
            days_by_id[day_id] = row
            days_by_date[day] = row
            report["record_days"] += 1
            report["changed"] = True
        if row.get("record_day_id") != day_id:
            row["record_day_id"] = day_id
            report["changed"] = True
        row.setdefault("date", day)
        row.setdefault("revision", 1)
        row.setdefault("updated_at", row.get("created_at", f"{day}T00:00:00"))

    for collection, date_field in (
        ("daily_records", "Date"),
        ("diet_records", "Date"),
        ("training_sessions", "Date"),
        ("data_module_records", "date"),
        ("raw_entries", "date"),
    ):
        for row in _rows(db, collection):
            day = canonical_date(row.get(date_field))
            if day and row.get("record_day_id") != record_day_id(day):
                row["record_day_id"] = record_day_id(day)
                report["changed"] = True

    raw_by_id = {str(row.get("id")): row for row in _rows(db, "raw_entries") if row.get("id")}
    for raw in _rows(db, "raw_entries"):
        if not raw.get("id"):
            raw["id"] = _stable_id("raw", {"date": raw.get("date"), "text": raw.get("text", "")})
            raw_by_id[str(raw["id"])] = raw
            report["changed"] = True
        raw_id = str(raw["id"])
        raw_revision_id = str(raw.get("raw_revision_id") or f"rawrev:{raw_id}:1")
        revisions = [item for item in _rows(db, "raw_entry_revisions") if str(item.get("raw_entry_id")) == raw_id]
        if not revisions:
            revision = {"raw_revision_id": raw_revision_id, "raw_entry_id": raw_id, "record_day_id": record_day_id(raw.get("date")), "date": canonical_date(raw.get("date")), "revision": 1, "text": str(raw.get("text", "")), "created_at": raw.get("created_at", ""), "updated_at": raw.get("updated_at", raw.get("created_at", "")), "source": raw.get("source", "legacy")}
            db["raw_entry_revisions"].append(revision)
            report["raw_revisions"] += 1
            report["changed"] = True
        raw["raw_revision_id"] = raw_revision_id
        raw.setdefault("revision", 1)
        raw.setdefault("updated_at", raw.get("created_at", ""))
        raw.setdefault("record_day_id", record_day_id(raw.get("date")))
        for revision in [item for item in _rows(db, "raw_entry_revisions") if str(item.get("raw_entry_id")) == raw_id]:
            revision.setdefault("raw_revision_id", raw_revision_id)
            revision.setdefault("revision", 1)
            revision.setdefault("record_day_id", record_day_id(revision.get("date")))
            revision.setdefault("date", canonical_date(raw.get("date")))
            revision.setdefault("updated_at", revision.get("created_at", ""))

    for definition in lexicon.get("movements", []) or []:
        if not isinstance(definition, dict):
            continue
        if not definition.get("revision"):
            definition["revision"] = 1
            report["changed"] = True
        if "updated_at" not in definition:
            definition["updated_at"] = definition.get("created_at", "")
            report["changed"] = True

    sessions = _rows(db, "training_sessions")
    for session in sessions:
        session_date = canonical_date(session.get("Date"))
        raw_text = str(session.get("Raw Record", "")).strip()
        candidates = [raw for raw in _rows(db, "raw_entries") if canonical_date(raw.get("date")) == session_date and not raw.get("superseded")]
        exact = [raw for raw in candidates if str(raw.get("text", "")).strip() == raw_text and raw_text]
        linked = exact[0] if len(exact) == 1 else candidates[0] if len(candidates) == 1 else None
        if linked:
            for key, value in (("raw_entry_id", linked.get("id")), ("raw_revision_id", linked.get("raw_revision_id"))):
                if session.get(key) != value:
                    session[key] = value
                    report["changed"] = True
        session.setdefault("record_day_id", record_day_id(session_date))

    session_by_id = {str(row.get("id")): row for row in sessions if row.get("id")}
    for movement in _movement_rows(db):
        movement_id = str(movement.get("movement_id", ""))
        for history in movement.get("history", []) or []:
            if history.get("training_session_id") not in session_by_id:
                day = canonical_date(history.get("date"))
                training_day = str(history.get("training_day", "")).strip()
                candidates = [row for row in sessions if canonical_date(row.get("Date")) == day and (not training_day or str(row.get("No.", "")).strip() == training_day)]
                if len(candidates) == 1:
                    history["training_session_id"] = candidates[0].get("id")
                    report["changed"] = True
            history.setdefault("record_day_id", record_day_id(history.get("date")))
            history.setdefault("movement_id", movement_id)
            linked = session_by_id.get(str(history.get("training_session_id")))
            if linked:
                if linked.get("raw_entry_id"):
                    history.setdefault("raw_entry_id", linked.get("raw_entry_id"))
                if linked.get("raw_revision_id"):
                    history.setdefault("raw_revision_id", linked.get("raw_revision_id"))

    db["record_schema_version"] = RELATION_SCHEMA_VERSION
    return db, lexicon, report


def validate_relations(database: dict, dictionary: dict) -> list[dict]:
    """Return invariant violations; an empty list means the graph is sound."""
    if database.get("record_schema_version") != RELATION_SCHEMA_VERSION:
        return []
    issues: list[dict] = []
    days = {str(row.get("record_day_id")): row for row in _rows(database, "record_days") if row.get("record_day_id")}
    sessions = {str(row.get("id")): row for row in _rows(database, "training_sessions") if row.get("id")}
    raw = {str(row.get("id")): row for row in _rows(database, "raw_entries") if row.get("id")}
    definitions = {str(row.get("movement_id")) for row in (dictionary.get("movements", []) if isinstance(dictionary, dict) else []) if row.get("movement_id")}
    history_ids: set[str] = set()
    for collection, date_field in (("daily_records", "Date"), ("diet_records", "Date"), ("training_sessions", "Date"), ("data_module_records", "date")):
        for row in _rows(database, collection):
            expected = record_day_id(row.get(date_field))
            if expected and str(row.get("record_day_id")) != expected:
                issues.append({"code": "RECORD_DAY_MISMATCH", "collection": collection, "id": row.get("id")})
            if expected and expected not in days:
                issues.append({"code": "MISSING_RECORD_DAY", "collection": collection, "id": row.get("id")})
    for movement in _movement_rows(database):
        movement_id = str(movement.get("movement_id", ""))
        if movement_id and definitions and movement_id not in definitions:
            issues.append({"code": "MISSING_MOVEMENT_DEFINITION", "movement_id": movement_id})
        for history in movement.get("history", []) or []:
            history_id = str(history.get("id", ""))
            if history_id in history_ids:
                issues.append({"code": "DUPLICATE_HISTORY_ID", "history_id": history_id})
            history_ids.add(history_id)
            session_id = str(history.get("training_session_id", ""))
            # A few pre-session legacy fixtures intentionally contain only a
            # movement archive.  Preserve those rows until a TrainingSession
            # exists; a real session-bearing database must be fully linked.
            same_day_has_session = any(canonical_date(row.get("Date")) == canonical_date(history.get("date")) for row in sessions.values())
            if same_day_has_session and (not session_id or session_id not in sessions):
                issues.append({"code": "ORPHAN_MOVEMENT_HISTORY", "history_id": history_id})
            raw_id = str(history.get("raw_entry_id", ""))
            if raw_id and raw_id not in raw:
                issues.append({"code": "ORPHAN_RAW_ENTRY", "history_id": history_id})
    return issues
